# Code signing (optional)

Windows shows *"Windows protected your PC"* (SmartScreen) for new programs that are not signed. Signing is **optional**; Sleepify works without it, people just click **More info → Run anyway**.

For open-source projects there is a free signing service, **SignPath Foundation**. In short:

1. Your repository must be public, use an OSI-approved license (MIT is), and the installer must be built automatically (the workflow in `.github/workflows/build.yml` does that).
2. Apply on the SignPath Foundation website and follow their onboarding (you need two-step verification on your accounts).
3. After they approve, they give you an organization id, a project slug and an API token. Add them in your repository: *Settings → Secrets and variables → Actions*.
4. Add SignPath's GitHub Action to the workflow after the "Build the installer" step, following **their** documentation (their instructions are the reference; the exact steps change over time).

A signature removes the "unknown publisher" name, but SmartScreen also looks at how many people have downloaded the file, so a warning may still appear for the first downloads.
