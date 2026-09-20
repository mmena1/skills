# Post-merge GitHub identity migration

Run this only after the standalone-repository cleanup has merged to the current fork's `main` and the merged commit has been pulled locally.

1. In the current GitHub repository settings, rename the fork from `mmena1/skills` to `mmena1/skills-fork-archive`.
2. Archive that renamed repository so it remains a read-only record of the fork history and PR #1.
3. Create a new, empty `mmena1/skills` repository from GitHub's new-repository flow. Do not create it as a fork, and do not initialize it with a README, license, or `.gitignore`.
4. In the local checkout of the merged `main`, preserve the archived repository as a non-canonical remote, add the new independent repository as `origin`, and push only `main`:

   ```bash
   git remote rename origin archive
   git remote set-url archive git@github.com:mmena1/skills-fork-archive.git
   git remote add origin git@github.com:mmena1/skills.git
   git remote remove upstream
   git push -u origin main
   ```

5. Confirm that `origin` points to the new repository and `archive` points to the renamed fork with `git remote -v`.
6. On GitHub, confirm the new repository does not show a "forked from" relationship. As an API check, verify that its repository record reports `fork: false` and has no `parent`.

Do not mirror obsolete branches, tags, releases, or pull-request metadata into the new repository unless that work is requested separately.
