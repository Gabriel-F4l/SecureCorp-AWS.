# SecureCorp AWS — Security CI runbook

## Purpose
The CI pipeline runs Python tests and synthesizes AWS CDK into a CloudFormation
template without deploying infrastructure or requiring AWS credentials.

## Workflow
- Triggered on pushes to `main` and `feature/security-ci`, and pull requests to `main`.
- Python 3.11 and Node.js 22 are installed on a GitHub-hosted runner.
- `pytest` validates synthesized infrastructure properties.
- `cdk synth` checks that the stack can produce CloudFormation.
- Bandit and Ruff initially run as **report-only** checks. They must be reviewed
  and converted into enforced checks after existing findings are triaged.

## Local commands
```powershell
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
cdk synth
```

## Failure response
1. Open GitHub → Actions → Security CI → failed run.
2. Read the failed step and its logs.
3. Reproduce locally with the commands above.
4. Fix the underlying code or test, then push to the feature branch.
5. Do not merge while required tests are failing.

## Security and cost guardrails
- CI must not contain AWS access keys or run `cdk deploy`.
- Synthesized templates may reveal infrastructure design; avoid committing secrets.
- Real deployments need a separate review of IAM, budget, costs, monitoring,
  rollback, and teardown. EC2 and interface endpoints may incur charges.
- The current tests cover selected invariants; they are not a comprehensive
  cloud security assessment.
