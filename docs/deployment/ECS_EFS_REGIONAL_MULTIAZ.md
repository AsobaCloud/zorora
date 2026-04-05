# ECS Fargate + EFS — Regional (Multi-AZ) for Zorora state

Zorora keeps SQLite and local state under **`/home/zorora/.zorora`** (see `Dockerfile` user `zorora`). On Fargate, that path is **lost on every new task** unless you mount **durable storage**.

This guide configures **Amazon EFS in Regional (Multi-AZ) mode** — **not** EFS One Zone.

## 1. Create the file system (Regional, Multi-AZ)

In the console: **EFS → Create file system** → choose **Regional** availability and durability (replicates across AZs in the region). Throughput: **Elastic** is typical. Encryption at rest: enabled.

CLI equivalent (no single-AZ flag — default is Regional):

```bash
aws efs create-file-system \
  --region af-south-1 \
  --creation-token zorora-prod-state \
  --performance-mode generalPurpose \
  --throughput-mode elastic \
  --encrypted
```

Create **mount targets** in **each subnet/AZ** the Fargate service uses (Regional EFS needs mount targets per AZ for VPC connectivity).

Optional but recommended: an **EFS access point** rooted at `/zorora` with POSIX user/group matching the container user (`zorora` in the image is UID **1000** unless you changed it).

## 2. Security groups

- EFS security group: allow **NFS (TCP 2049)** inbound from the **Fargate tasks security group** (or the whole task ENI SG).
- Tasks must reach the mount targets in their VPC.

## 3. IAM

Task execution role: unchanged for EFS.

Task role: attach a policy allowing `elasticfilesystem:ClientMount` (and `ClientWrite` if not read-only) on the file system or access point ARN. Required when `efsVolumeConfiguration.authorizationConfig.iam` is **ENABLED**.

## 4. ECS task definition — volumes + mount (Multi-AZ EFS)

Add a volume of type **EFS** pointing at your **Regional** file system. **`transitEncryption`** should be **ENABLED** for Fargate.

Example fragment (merge into your existing `containerDefinitions` / `volumes`; replace IDs):

```json
{
  "volumes": [
    {
      "name": "zorora-zorora-home",
      "efsVolumeConfiguration": {
        "fileSystemId": "fs-0123456789abcdef0",
        "transitEncryption": "ENABLED",
        "authorizationConfig": {
          "accessPointId": "fsap-0123456789abcdef0",
          "iam": "ENABLED"
        }
      }
    }
  ]
}
```

```json
"mountPoints": [
  {
    "sourceVolume": "zorora-zorora-home",
    "containerPath": "/home/zorora/.zorora",
    "readOnly": false
  }
]
```

If you omit an access point, you can mount the file system root; access points reduce blast radius and enforce UID/GID.

**Platform version:** Fargate tasks need a platform version that supports EFS (e.g. **1.4.0+** on Linux).

## 5. SQLite on NFS

SQLite on network file systems can be problematic under concurrency. For **one writer** (single Fargate task / one gunicorn worker) it is often acceptable; for **multiple tasks or many writers**, prefer **RDS**, **DynamoDB**, or another service designed for shared transactional state.

## 6. Cost reference (`af-south-1`)

Regional (Multi-AZ) **EFS Standard** storage is listed at **$0.39 / GB-month** on the public AWS price list (verify in [EFS pricing](https://aws.amazon.com/efs/pricing/)). Throughput and data transfer are additional.
