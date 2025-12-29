# Zorora REPL Operational Contract

## Purpose

This document defines the operational contract for using Zorora REPL to interact with ONA platform ML model observation workflows.

## Authority & Access

### Who Can Use Zorora

- **ML Engineers**: Full access to all commands
- **Data Scientists**: Read-only access + promotion with approval
- **Platform Operators**: Read-only access + emergency rollback
- **External Users**: No access (internal-only tool)

### Authentication

- **Primary**: AWS IAM role assumption (recommended)
- **Fallback**: Internal API token (for development)

### Access Control

- All API requests require authentication
- Actor identity is logged in all audit events
- Force promotions require elevated permissions

## Command Usage

### Read-Only Commands (Safe)

These commands do not modify state:

- `ml-list-challengers <customer_id>`: List challenger models
- `ml-show-metrics <model_id>`: Show evaluation metrics
- `ml-diff <challenger_id> <production_id>`: Compare models
- `ml-audit-log <customer_id>`: View audit log

**No approval required** for read-only commands.

### Mutating Commands (Require Approval)

These commands modify production state:

- `ml-promote <customer_id> <model_id> <reason> [--force]`: Promote challenger
- `ml-rollback <customer_id> <reason>`: Rollback production

**Requirements**:
- `reason` argument is mandatory (minimum 10 characters)
- Confirmation prompt required
- `--force` requires extra confirmation
- All actions logged to audit trail

## Promotion Rules

### When Promotion Is Allowed

1. **Gate 1: Backtest Superiority**
   - MAE improvement ≥5% OR RMSE improvement ≥5%
   - Consistent across evaluation windows (≥12 windows)

2. **Gate 2: No Seasonal Regression**
   - Performance not worse in any major season
   - Seasonal analysis shows consistent improvement

3. **Gate 3: Metrics Current**
   - Evaluation completed within last 7 days
   - Metrics not stale

4. **Gate 4: Human Approval**
   - Reviewer has reviewed backtest results
   - Reviewer has reviewed seasonal analysis
   - Reviewer has documented reason

### When `--force` Must Be Used

- Emergency rollback needed
- Experimental promotion for testing
- Metrics are stale but promotion still desired
- Requires explicit justification in reason field

**Warning**: `--force` bypasses safety gates. Use only when necessary.

## Rollback Rules

### When Rollback Is Allowed

- Production model showing degradation
- Emergency situations
- Post-promotion issues detected
- Always allowed (no gates)

### Rollback Process

1. Previous production model restored from archive
2. Current production archived
3. Registry updated
4. Audit event logged

## Audit Log Review

### Who Reviews Audit Logs

- **Weekly**: ML Engineering team lead
- **Post-Incident**: Platform operations team
- **On-Demand**: Any authorized user via `ml-audit-log`

### What to Look For

- Unauthorized promotions
- Promotions without proper review
- Frequent use of `--force` flag
- Rollbacks without documented reasons

## Operational Procedures

### Pre-Promotion Checklist

- [ ] Review backtest results (`ml-show-metrics`)
- [ ] Compare challenger vs production (`ml-diff`)
- [ ] Verify metrics are current (<7 days)
- [ ] Check for seasonal regressions
- [ ] Document promotion reason
- [ ] Get approval if required

### Post-Promotion Monitoring

- Monitor CloudWatch metrics for 24 hours
- Check operational telemetry for degradation
- Be prepared to rollback if issues detected

### Emergency Procedures

1. **Production Model Degraded**
   - Use `ml-rollback` immediately
   - Document reason in rollback command
   - Investigate root cause

2. **Unauthorized Promotion Detected**
   - Review audit log (`ml-audit-log`)
   - Identify actor
   - Rollback if necessary
   - Report security incident

## Best Practices

1. **Always Use Reason**
   - Document why promotion/rollback is needed
   - Minimum 10 characters
   - Be specific and clear

2. **Review Before Promoting**
   - Always run `ml-diff` before promotion
   - Verify metrics are current
   - Check for regressions

3. **Avoid `--force`**
   - Only use when absolutely necessary
   - Document justification in reason
   - Get approval before using

4. **Monitor After Changes**
   - Check CloudWatch metrics
   - Review operational telemetry
   - Be ready to rollback

5. **Keep Audit Trail Clean**
   - Use clear, descriptive reasons
   - Follow promotion checklist
   - Review audit logs regularly

## Troubleshooting

### "Challenger not found"
- Verify customer_id is correct
- Check challenger exists in registry
- Use `ml-list-challengers` to see available challengers

### "Metrics are stale"
- Re-evaluate challenger model
- Use `--force` if re-evaluation not possible (with approval)

### "Challenger does not meet promotion gates"
- Review evaluation summary
- Check for seasonal regressions
- Use `ml-diff` to see detailed comparison
- Use `--force` only with approval

### "Unauthorized" error
- Check authentication credentials
- Verify IAM role or API token
- Contact platform operations team

### "Connection error" or "API Error"
- Verify `ONA_API_BASE_URL` environment variable is set correctly
- Check network connectivity to ONA platform
- Verify `ONA_API_TOKEN` or `ONA_USE_IAM` is configured
- Check API endpoint is accessible

## Configuration

### Environment Variables

Zorora ONA platform commands require the following environment variables:

- `ONA_API_BASE_URL`: ONA platform API base URL (default: `https://p0c7u3j9wi.execute-api.af-south-1.amazonaws.com/api/v1`)
- `ONA_API_TOKEN`: Authentication token for ONA platform API (required if not using IAM)
- `ONA_USE_IAM`: Use IAM authentication (default: `false`)

### Example Configuration

```bash
# Using Bearer token authentication (recommended for development)
export ONA_API_BASE_URL="https://p0c7u3j9wi.execute-api.af-south-1.amazonaws.com/api/v1"
export ONA_API_TOKEN="your-api-token-here"
export ONA_USE_IAM="false"

# Using IAM authentication (production)
export ONA_API_BASE_URL="https://p0c7u3j9wi.execute-api.af-south-1.amazonaws.com/api/v1"
export ONA_USE_IAM="true"
# AWS credentials should be configured via AWS CLI or IAM role
```

### Quick Setup

Retrieve credentials from AWS SSM Parameter Store:

```bash
# Run the credentials script
./scripts/get-global-training-api-credentials.sh

# Or manually retrieve from SSM:
export ONA_API_BASE_URL=$(aws ssm get-parameter --name /ona-platform/prod/global-training-api-endpoint --query 'Parameter.Value' --output text)
export ONA_API_TOKEN=$(aws ssm get-parameter --name /ona-platform/prod/global-training-api-token --with-decryption --query 'Parameter.Value' --output text)
```

## Contact

- **ML Engineering**: ml-team@company.com
- **Platform Operations**: platform-ops@company.com
- **Security Issues**: security@company.com

---

**Document Status**: Active  
**Last Updated**: 2025-01-23  
**Version**: 1.0.0
