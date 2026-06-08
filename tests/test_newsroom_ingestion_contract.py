from datetime import date
from unittest.mock import patch

from botocore.exceptions import ClientError

from tools.research import newsroom_dynamodb


class _FakeResource:
    def __init__(self, table):
        self._table = table

    def Table(self, _name):
        return self._table


class _SizeGuardTable:
    def __init__(self):
        self.last_item = None

    def get_item(self, Key):
        return {}

    def put_item(self, Item, **kwargs):
        if len(Item.get("full_content", "").encode("utf-8")) >= 400 * 1024:
            raise AssertionError("oversized DynamoDB item")
        self.last_item = Item
        return {}


class _RaceConditionTable:
    def __init__(self, existing_item):
        self.items = {(existing_item["PK"], existing_item["SK"]): dict(existing_item)}
        self.put_calls = []

    def get_item(self, Key):
        return {}

    def put_item(self, Item, ConditionExpression=None, **kwargs):
        self.put_calls.append({"Item": Item, "ConditionExpression": ConditionExpression})
        key = (Item["PK"], Item["SK"])
        if key in self.items and ConditionExpression is not None:
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException", "Message": "duplicate"}},
                "PutItem",
            )
        self.items[key] = dict(Item)
        return {}



def _metadata(full_content, **overrides):
    data = {
        "url": "https://example.com/articles/grid-update",
        "title": "Grid update",
        "source": "Desk",
        "pub_date": date.today().isoformat(),
        "collection_date": f"{date.today().isoformat()}T12:00:00Z",
        "content_length": len(full_content),
        "description": "grid update description",
        "full_content": full_content,
        "tags": {
            "core_topics": ["energy"],
            "special_tags": [],
            "matched_keywords": ["grid"],
            "continents": ["Africa"],
            "countries": ["South Africa"],
        },
    }
    data.update(overrides)
    return data



def test_insert_article_truncates_oversized_full_content_before_write():
    huge_content = "x" * (450 * 1024)
    table = _SizeGuardTable()

    with patch.object(newsroom_dynamodb, "_get_dynamodb", return_value=_FakeResource(table)):
        inserted = newsroom_dynamodb.insert_article(_metadata(huge_content))

    assert inserted is True
    assert table.last_item is not None
    assert len(table.last_item["full_content"].encode("utf-8")) < 400 * 1024
    assert table.last_item["full_content"] != huge_content



def test_insert_article_returns_false_for_duplicate_race_instead_of_overwriting():
    metadata = _metadata("original body")
    pk = f"ARTICLE#{newsroom_dynamodb._url_hash(metadata['url'])}"
    sk = newsroom_dynamodb._parse_date_to_sort_key(metadata["pub_date"])
    existing_item = {
        "PK": pk,
        "SK": sk,
        "url": metadata["url"],
        "title": metadata["title"],
        "source": metadata["source"],
        "pub_date": metadata["pub_date"],
        "collection_date": metadata["collection_date"],
        "content_length": len("original body"),
        "core_topics": ["energy"],
        "special_tags": [],
        "matched_keywords": ["grid"],
        "continents": ["Africa"],
        "countries": ["South Africa"],
        "description": "existing description",
        "full_content": "original body",
        "date_key": sk,
        "pub_timestamp": newsroom_dynamodb._parse_timestamp(metadata["pub_date"]),
        "collection_key": f"COLLECTED#{metadata['collection_date'][:10]}",
        "source_key": "SOURCE#Desk",
        "topic_key": "TOPIC#energy",
    }
    table = _RaceConditionTable(existing_item)

    with patch.object(newsroom_dynamodb, "_get_dynamodb", return_value=_FakeResource(table)):
        inserted = newsroom_dynamodb.insert_article(_metadata("new body"))

    assert inserted is False
    assert table.items[(pk, sk)]["full_content"] == "original body"
