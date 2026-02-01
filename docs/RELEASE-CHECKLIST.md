# Release Checklist

This checklist ensures a smooth and reliable release process for the Labgrid Dashboard.

## Pre-Release

### Code Quality

- [ ] All tests pass: `cd backend && python -m pytest`
- [ ] Code coverage meets minimum threshold (80%): `pytest --cov=app --cov-report=term`
- [ ] Frontend builds without errors: `cd frontend && npm run build`
- [ ] No TypeScript errors: `cd frontend && npm run type-check` (if available)
- [ ] Linting passes: `cd frontend && npm run lint` (if configured)
- [ ] No critical security vulnerabilities: `npm audit` and `pip-audit` (if available)

### Documentation

- [ ] CHANGELOG.md updated with release notes
- [ ] Version bumped in `frontend/package.json`
- [ ] README.md reflects new features/changes
- [ ] DEPLOYMENT.md is up to date
- [ ] API documentation updated (if applicable)

### Testing

- [ ] Local production build tested:
  ```bash
  ./scripts/test-production-image.sh
  ```
- [ ] Manual testing completed:
  - [ ] Dashboard loads correctly
  - [ ] WebSocket connection works
  - [ ] Commands execute successfully
  - [ ] Presets can be selected
  - [ ] Health endpoints respond
- [ ] Tested with real coordinator (not just mock/staging)
- [ ] Tested on both amd64 and arm64 (if possible)

### Version Control

- [ ] All changes committed to feature branch
- [ ] Feature branch merged to main (or release branch)
- [ ] No uncommitted changes: `git status`
- [ ] Working directory is clean

## Release

### Create Release

- [ ] Determine version number (follow [Semantic Versioning](https://semver.org/)):
  - MAJOR: Breaking changes
  - MINOR: New features (backward compatible)
  - PATCH: Bug fixes
- [ ] Create annotated git tag:
  ```bash
  git tag -a v1.2.3 -m "Release v1.2.3"
  ```
- [ ] Push tag to trigger GitHub Actions:
  ```bash
  git push origin v1.2.3
  ```

### Monitor Build

- [ ] GitHub Actions workflow started: https://github.com/Gerrri/labgrid-dashboard/actions
- [ ] Workflow completed successfully
- [ ] No build errors or warnings
- [ ] Check build logs for issues

### Verify Publication

- [ ] Image published to GHCR: https://github.com/Gerrri/labgrid-dashboard/pkgs/container/labgrid-dashboard
- [ ] All expected tags created:
  - [ ] `v1.2.3` (exact version)
  - [ ] `1.2.3` (without 'v' prefix)
  - [ ] `1.2` (minor version)
  - [ ] `1` (major version)
  - [ ] `latest` (if releasing from main)
- [ ] Multi-architecture images available (amd64, arm64):
  ```bash
  docker manifest inspect ghcr.io/gerrri/labgrid-dashboard:v1.2.3
  ```

## Post-Release

### Deployment Testing

- [ ] Pull new image:
  ```bash
  docker pull ghcr.io/gerrri/labgrid-dashboard:1.2.3
  ```
- [ ] Test deployment with production compose:
  ```bash
  docker compose -f docker-compose.prod.yml up -d
  ```
- [ ] Verify health endpoints:
  ```bash
  curl http://localhost/health
  curl http://localhost/api/health
  ```
- [ ] Test in browser:
  - [ ] Dashboard loads
  - [ ] WebSocket connects
  - [ ] Commands execute
  - [ ] No console errors

### Documentation

- [ ] Update README.md with latest version in examples
- [ ] Create GitHub release with changelog:
  - Go to: https://github.com/Gerrri/labgrid-dashboard/releases/new
  - Select tag: v1.2.3
  - Title: "Release v1.2.3"
  - Description: Copy from CHANGELOG.md
  - Publish release

### Communication

- [ ] Announce release (if applicable):
  - [ ] Internal team notification
  - [ ] User documentation updated
  - [ ] Release notes published

### Package Visibility

- [ ] Set package visibility to public (first release only):
  1. Go to package settings: https://github.com/Gerrri/labgrid-dashboard/pkgs/container/labgrid-dashboard/settings
  2. Change visibility to "Public"
  3. Confirm the change

## Rollback Plan

If issues are discovered after release:

### Quick Fix (Patch Release)

1. Create hotfix branch from the release tag:
   ```bash
   git checkout -b hotfix/v1.2.4 v1.2.3
   ```
2. Fix the issue and commit
3. Create new patch release:
   ```bash
   git tag -a v1.2.4 -m "Hotfix v1.2.4"
   git push origin v1.2.4
   ```

### Rollback to Previous Version

1. Users can roll back by pinning to previous version:
   ```bash
   docker pull ghcr.io/gerrri/labgrid-dashboard:1.2.2
   ```
2. Update documentation to recommend previous version
3. Investigate and fix the issue
4. Release new version when ready

### Remove Bad Release

If a release is critically broken:

1. Delete the git tag locally and remotely:
   ```bash
   git tag -d v1.2.3
   git push origin :refs/tags/v1.2.3
   ```
2. Delete package version from GHCR (if possible)
3. Document the issue in CHANGELOG.md
4. Release a fixed version

## Release Schedule

- **Patch releases**: As needed for bug fixes
- **Minor releases**: Monthly or when significant features are ready
- **Major releases**: Annually or when breaking changes are necessary

## Version Support

- **Latest major version**: Full support
- **Previous major version**: Security fixes only
- **Older versions**: No support (recommend upgrade)

## Notes

- Always test releases in a staging environment before production
- Keep CHANGELOG.md up to date with every release
- Use GitHub Discussions or Issues for release-related questions
- Monitor release metrics: downloads, stars, issues after release
- Per project rules: NO "Co-Authored-By: Claude" in commit messages
