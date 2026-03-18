---
title: "Set Up an Automated Mobile App Release Pipeline with AI"
slug: set-up-automated-mobile-app-release-pipeline
description: "Use AI to configure CI/CD for iOS and Android builds, automate versioning, and streamline app store submissions."
skills: [cicd-pipeline, changelog-generator, coding-agent]
category: devops
tags: [mobile, release, ci-cd, app-store, automation]
---

# Set Up an Automated Mobile App Release Pipeline with AI

## The Problem

Nadia leads a mobile team of four that ships a React Native app to both iOS and Android. Every release takes two developer-days. The process looks like this: one developer manually bumps version numbers in four files (package.json, Info.plist, build.gradle versionCode, build.gradle versionName). Another opens Xcode and builds the iOS archive, then opens Android Studio for the Android bundle. A third writes release notes from memory -- "I think we fixed that crash on Android 14? And there was a biometric login feature, right?" Someone uploads both binaries to App Store Connect and Google Play Console by hand.

Builds fail silently when signing certificates expire. Version codes get reused, which Google Play rejects with a confusing error. Release notes are inconsistent between platforms -- the iOS description mentions features that aren't on Android yet, and vice versa. The team ships biweekly but wants to move to weekly releases. At two developer-days per release, that means burning 40% of the team's capacity on the release process alone. Impossible.

## The Solution

Use the **cicd-pipeline** skill to scaffold a GitHub Actions workflow that builds, signs, and uploads both platforms on every tagged commit. Add the **changelog-generator** skill to auto-generate release notes from merged PRs. Use the **coding-agent** skill to write and maintain the Fastlane configuration that handles code signing, screenshots, and store metadata.

## Step-by-Step Walkthrough

### Step 1: Scaffold the CI/CD Workflow

The foundation: a GitHub Actions workflow that triggers on version tags and builds both platforms in parallel.

```text
Create a GitHub Actions workflow for our React Native app. It should trigger on tags matching v*. Build the iOS .ipa using Fastlane and the Android .aab using Gradle. Store both artifacts. Use separate jobs for iOS (macos-latest) and Android (ubuntu-latest).
```

The workflow (`.github/workflows/release.yml`) splits iOS and Android into parallel jobs because they run on different operating systems and neither depends on the other:

```yaml
name: Release
on:
  push:
    tags: ['v*']

jobs:
  ios:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ruby/setup-ruby@v1
      - run: bundle exec fastlane ios build
      - uses: actions/upload-artifact@v4
        with:
          name: ios-ipa
          path: output/app.ipa

  android:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          java-version: '17'
      - run: ./gradlew bundleRelease
      - uses: actions/upload-artifact@v4
        with:
          name: android-aab
          path: android/app/build/outputs/bundle/release/app-release.aab
```

Both jobs run simultaneously. iOS takes about 12 minutes (Xcode build is the bottleneck), Android takes about 8 minutes. Total wall-clock time: 12 minutes instead of the 2+ hours a developer spent doing this manually with context switches.

### Step 2: Configure Code Signing and Fastlane

Code signing is where mobile releases go to die. Certificates expire, provisioning profiles get out of sync, and the keystore password is in a Slack message from 2023. Fastlane handles all of this declaratively.

```text
Write Fastlane configurations for both platforms. iOS should use match for certificate management with our git-based signing repo. Android should read the keystore from a GitHub secret. Add lanes for build, beta (TestFlight / internal track), and production.
```

**iOS** (`ios/fastlane/Fastfile`): Three lanes -- `build`, `beta`, and `production`. The `match` integration stores certificates and provisioning profiles in a private Git repo. When a certificate expires, `match` generates a new one automatically. No more emergency Slack messages at release time.

**Android** (`android/fastlane/Fastfile`): Same three lanes. The keystore is base64-encoded in a GitHub Actions secret (`ANDROID_KEYSTORE_BASE64`), decoded at build time, and never touches a developer's machine. The keystore password lives in a separate secret.

Both configurations include error handling for the most common failure modes: expired certificates get flagged with a clear error message instead of a cryptic Xcode build failure, and version code conflicts get caught before the upload attempt.

### Step 3: Auto-Generate Release Notes

Release notes written from memory are unreliable. Release notes generated from the actual commit history are accurate by definition.

```text
Add a step to the release workflow that generates release notes from all merged PRs since the last tag. Group changes into Features, Fixes, and Maintenance. Write the output to CHANGELOG.md and use it as the release body on GitHub.
```

The changelog generator reads PR titles and labels since the last Git tag and groups them:

```markdown
## v2.4.0 (2025-01-20)

### Features
- Add biometric login support (#142)
- Implement offline mode for saved articles (#138)

### Fixes
- Fix crash on Android 14 when opening camera (#145)
- Resolve push notification badge count not clearing (#141)

### Maintenance
- Upgrade React Native to 0.73.2 (#139)
```

This output goes to three places: `CHANGELOG.md` in the repo, the GitHub Release body, and the store submission metadata for both platforms. Consistent release notes everywhere, generated from the same source, with zero manual writing.

The grouping relies on PR labels: `feature`, `fix`, `maintenance`. If a PR has no label, it falls into an "Other" category that's visible in the changelog -- which trains the team to label their PRs because unlabeled ones look sloppy in the release notes.

### Step 4: Automate Store Submissions

Building the binaries is only half the release. The other half -- uploading to App Store Connect and Google Play Console, filling in metadata, selecting the right track -- is equally tedious and error-prone.

```text
Add Fastlane lanes that upload the iOS build to TestFlight and the Android bundle to Google Play internal testing track automatically after a successful build. Include store metadata (description, screenshots path, release notes) from a metadata/ directory.
```

After a successful build, Fastlane uploads automatically:

- **iOS**: The `.ipa` goes to TestFlight with the generated release notes. App Store Connect metadata (description, keywords, screenshots) lives in `metadata/ios/` and stays version-controlled with the code.
- **Android**: The `.aab` goes to Google Play's internal testing track with the same release notes. Store listing metadata lives in `metadata/android/`.

Promoting from internal testing to production is a separate, intentional step -- the team reviews the build in TestFlight and internal testing before pushing the button for public release. Automation handles the mechanical work; humans make the go/no-go decision.

### Step 5: Add Version Bumping Automation

The last manual step: bumping version numbers in four files. One command replaces all of it.

```text
Write a script that reads the current version from package.json, bumps it (major/minor/patch based on a parameter), updates package.json, ios/Info.plist, and android/app/build.gradle versionCode and versionName, commits the changes, and creates a git tag. Run it with: ./scripts/bump-version.sh minor
```

The script (`scripts/bump-version.sh`) takes one argument -- `major`, `minor`, or `patch` -- and does everything:

1. Reads current version from `package.json` (e.g., `2.3.1`)
2. Bumps according to the argument (minor: `2.3.1` -> `2.4.0`)
3. Updates `package.json`, `ios/Info.plist` (CFBundleShortVersionString), and `android/app/build.gradle` (both `versionCode` and `versionName`)
4. Commits with message `chore: bump version to 2.4.0`
5. Creates git tag `v2.4.0`

The full release process is now two commands:

```bash
./scripts/bump-version.sh minor
git push --tags
```

The tag push triggers the GitHub Actions workflow, which builds both platforms, signs them, generates release notes, and uploads to both stores. From typing the command to having builds in TestFlight and Google Play internal testing: 18 minutes.

## Real-World Example

Nadia's team starts using the pipeline on a Tuesday. The first automated release goes out Wednesday morning -- what used to take two developer-days finishes while the team is having their standup. The changelog generator picks up all 6 PRs merged since the last tag and groups them cleanly.

The following week, the CI job catches something the team hadn't noticed: the iOS distribution certificate is expiring in 19 days. The build log flags it as a warning with a link to the renewal process. Under the old manual workflow, they would have discovered this on release day when the Xcode build failed -- probably triggering a two-hour scramble to generate a new certificate, update the provisioning profile, and rebuild.

After one month: time spent on releases drops from 16 hours per month to under one hour. The team moves to weekly releases because the mechanical cost is nearly zero. Version codes never conflict because the bump script calculates them deterministically. Release notes are always accurate because they come from PR history, not human memory. The four developers who used to spend release days on the process now ship features on release days instead.
