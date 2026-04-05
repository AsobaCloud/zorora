# ona-zorora-prod — Regional (Multi-AZ) EFS applied

Applied in **af-south-1** so Fargate tasks keep SQLite and local state under **`/home/zorora/.zorora`**.

| Resource | ID / ARN fragment |
|----------|-------------------|
| EFS file system (Regional, Elastic throughput, encrypted) | `fs-066661f81af6a1128` |
| EFS access point (POSIX 1000:1000, root `/zorora`) | `fsap-0766807bad409ae0c` |
| EFS security group (NFS 2049 from task SG) | `sg-0cbcae3e20b49679a` |
| Task security group (source for NFS rule) | `sg-0355a648eecb65f29` |
| Mount targets | `fsmt-07fd210dc35e2e01a`, `fsmt-0df1b4245a28ae61f`, `fsmt-0e876146cff8a22e1` (one per service subnet) |
| ECS task definition with volume + mount | `ona-zorora-prod:4` |

**Task definition change:** volume `zorora-zorora-home` → `efsVolumeConfiguration` on `fs-066661f81af6a1128`, `transitEncryption` **ENABLED**, access point `fsap-0766807bad409ae0c`, `iam` **DISABLED** (SG-based auth). Container `ona-zorora` mount **`/home/zorora/.zorora`**.

**Do not** re-run `create-file-system` for this environment; it would create duplicate spend. To change sizing or options, use the existing file system.

**Drift:** ECS desired configuration is now **`ona-zorora-prod:4`**. If infra is recreated elsewhere (Terraform, CDK), import or mirror these resources so the service does not revert to a task definition without EFS.

## Seeding EFS from a machine that still has `~/.zorora`

Anything that existed **only** on Fargate **before** EFS was mounted is **not recoverable** from AWS. To copy data you still have locally (or from a backup tree) onto this EFS:

1. Task definition **`ona-zorora-prod-efs-migrate:1`** — Alpine one-shot, same EFS + access point, extracts a tarball into the mount (`/data` → access point root).
2. Script: [`scripts/migrate_local_zorora_to_prod_efs.sh`](scripts/migrate_local_zorora_to_prod_efs.sh) — tars the directory, uploads to S3, presigns, runs the task, waits for exit 0.
3. Default bucket: **`ona-zorora-prod-user-state-migrate`** (override with `ZORORA_MIGRATE_BUCKET`). **Delete the uploaded object after a successful run** to avoid leaving a full copy in S3.

**Done once (2026-04-05):** Local `~/.zorora` from the operator machine was migrated successfully; migration task logs show `imaging_data.db`, `zorora.db`, `market_data.db`, etc. on EFS with owner **1000:1000**.
