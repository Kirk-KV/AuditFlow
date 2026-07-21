# Git Collaboration and Review

Git can keep the version history of AuditFlow source files. Manager approval and comments require a private Git service with pull/merge requests, such as GitLab, Azure DevOps, GitHub Enterprise, or an approved equivalent.

## One-Time Setup

Configure the repository so that:

- `main` is protected;
- direct pushes and force-pushes to `main` are disabled;
- every change requires a pull/merge request;
- at least one audit manager approval is required;
- unresolved comments block merging;
- access, retention, backups, and audit logs follow company policy.

Git contains audit working documents and analysis scripts. Raw data, regulations, correspondence, screenshots, secrets, rendered files, and AI output remain outside Git. The generated `.gitignore` applies these exclusions.

## Auditor Workflow

Create a branch for one logical change:

```bash
git switch main
git pull --ff-only
git switch -c audit/update-procurement-program
```

After editing:

```bash
auditflow validate
auditflow evidence status
git status
git add <changed_source_files>
git commit -m "Update procurement audit program"
git push -u origin audit/update-procurement-program
```

Open a pull/merge request and describe what changed and why. The manager comments on specific lines, requests changes, or approves. Corrections should normally be added as new commits to the same branch so the discussion remains traceable.

After approval, merge through the server interface and update the local copy:

```bash
git switch main
git pull --ff-only
```

## Undoing Changes

- Uncommitted file: `git restore <path>`.
- Unmerged branch: correct it with another commit or close the pull/merge request.
- Shared or merged commit: use `git revert <commit_sha>` and review the revert through a new pull/merge request.

Avoid rewriting shared history. A revert preserves who changed what, why it was reversed, and who approved the reversal.

## Evidence Hashes

The first `auditflow evidence refresh` creates `04_evidence/evidence_manifest.yml`. Git tracks this path/size/SHA-256 list while evidence contents remain outside Git.

Check for local differences:

```bash
auditflow evidence status
```

When an evidence addition, replacement, or deletion is intentional:

```bash
auditflow evidence refresh
git add 04_evidence/evidence_manifest.yml
git commit -m "Record updated evidence fingerprints"
```

The pull/merge request then shows the changed hash. A hash proves only whether the local file matches the recorded fingerprint; it does not replace secure evidence storage, access controls, or authenticity checks.
