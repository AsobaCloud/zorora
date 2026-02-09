import unittest

from simplified_router import SimplifiedRouter


class SimplifiedRouterTests(unittest.TestCase):
    def setUp(self):
        self.router = SimplifiedRouter()

    def test_routes_code_request_to_code_workflow(self):
        result = self.router.route("Implement a python function to parse CSV content")
        self.assertEqual(result["workflow"], "code")
        self.assertEqual(result.get("tool"), "use_coding_agent")

    def test_routes_file_request_to_file_op_workflow(self):
        result = self.router.route("show my saved research")
        self.assertEqual(result["workflow"], "file_op")
        self.assertEqual(result["action"], "read_file")

    def test_defaults_to_research_workflow(self):
        result = self.router.route("hello there")
        self.assertEqual(result["workflow"], "research")
        self.assertEqual(result["action"], "multi_source_research")


if __name__ == "__main__":
    unittest.main()
