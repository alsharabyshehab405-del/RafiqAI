# Release Runbook

1. Merge to main.
2. Wait for Backend, Android, Security and Integration workflows to pass.
3. Configure production secrets and variables.
4. Build signed APK/AAB from GitHub Actions.
5. Verify artifact hashes and versionCode.
6. Deploy backend to staging.
7. Run smoke tests.
8. Run database backup.
9. Deploy production API with rolling replicas.
10. Monitor errors/latency/cost for at least one observation window.
11. Upload AAB to Google Play Internal Testing.
12. Test subscription, restore, deletion, memory and file flows.
13. Promote gradually to production.

Rollback: stop rollout, restore the previous application container, and use forward database fixes unless the migration has an explicitly tested rollback.
