# Git Cheatsheet (Intermediate Developer)

A practical reference for the commands you will use most often in daily development.

## 1) Daily Workflow (Most Used)

### Check what changed
```bash
git status
git diff
git diff --staged
```

### Stage and commit
```bash
git add <file>
git add .
git commit -m "feat: add Y-bus validation"
```

### Pull latest changes safely
```bash
git fetch
git pull --rebase
```

### Push your branch
```bash
git push
git push -u origin <branch>
```

### Branch switching and creation
```bash
git switch <branch>
git switch -c <new-branch>
```

---

## 2) Inspect History and Changes

### Read commit history
```bash
git log --oneline --graph --decorate --all
git log -p
git show <commit>
```

### Compare branches or commits
```bash
git diff main...feature-branch
git diff <commit1> <commit2>
```

### See who changed a line
```bash
git blame <file>
```

---

## 3) Fix Mistakes Quickly

### Unstage a file
```bash
git restore --staged <file>
```

### Discard local file changes
```bash
git restore <file>
```

### Amend last commit (message or staged changes)
```bash
git commit --amend
```

### Undo a commit safely (shared branch)
```bash
git revert <commit>
```

### Move branch pointer (local history rewrite)
```bash
git reset --soft HEAD~1   # keep changes staged
git reset --mixed HEAD~1  # keep changes unstaged (default)
git reset --hard HEAD~1   # discard changes completely
```

---

## 4) Branch and Integration Work

### Rebase your branch onto latest main
```bash
git fetch origin
git rebase origin/main
```

### Continue after conflict resolution
```bash
git add <resolved-files>
git rebase --continue
```

### Abort an in-progress rebase
```bash
git rebase --abort
```

### Merge (non-rebase flow)
```bash
git merge <branch>
```

### Cherry-pick specific commit
```bash
git cherry-pick <commit>
```

---

## 5) Stash Work In Progress

### Save current uncommitted work
```bash
git stash
git stash push -m "wip: jacobian debugging"
```

### Restore stashed work
```bash
git stash list
git stash pop
git stash apply stash@{1}
```

---

## 6) Remote Management

### Inspect remotes
```bash
git remote -v
```

### Add or update remote URL
```bash
git remote add origin <url>
git remote set-url origin <url>
```

### Remove deleted remote branches locally
```bash
git fetch --prune
```

---

## 7) Useful Cleanup

### Delete local and remote branches
```bash
git branch -d <branch>
git branch -D <branch>                 # force delete
git push origin --delete <branch>
```

### Show unreachable/garbage candidates
```bash
git gc --prune=now
```

---

## 8) Tags (Releases)

### Create and push tags
```bash
git tag -a v1.2.0 -m "release v1.2.0"
git push origin v1.2.0
git push --tags
```

### List tags
```bash
git tag
git tag -l "v1.*"
```

---

## 9) Recommended Aliases

Add to your global Git config:

```bash
git config --global alias.st "status -sb"
git config --global alias.co "switch"
git config --global alias.br "branch"
git config --global alias.cm "commit -m"
git config --global alias.lg "log --oneline --graph --decorate --all"
```

Usage examples:
```bash
git st
git lg
```

---

## 10) Oh My Zsh Git Plugin (Most Used Aliases)

If you use Oh My Zsh with the `git` plugin, these aliases speed up daily work.

### Common aliases
```bash
gst                 # git status
ga <file>           # git add <file>
gaa                 # git add --all
gcmsg "message"     # git commit -m "message"
gcam "message"      # git commit -a -m "message"
gco <branch>        # git checkout <branch>
gcb <new-branch>    # git checkout -b <new-branch>
gb                  # git branch
gba                 # git branch -a
gd                  # git diff
gds                 # git diff --staged
gl                  # git pull
gp                  # git push
gpf                 # git push --force-with-lease
glog                # pretty graph log
grh                 # git reset
grhh                # git reset --hard
gclean              # cleanup merged local branches
```

### List aliases available in your shell
```bash
alias | grep '^g'
```

---

## 11) Safe Team Habits

- Prefer `git pull --rebase` for cleaner history on feature branches.
- Use `git revert` instead of history rewrites on shared branches.
- Push smaller commits with clear messages.
- Run tests before pushing.
- Avoid `git push --force`; if required, use `git push --force-with-lease`.

```bash
git push --force-with-lease
```
