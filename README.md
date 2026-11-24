# Magpie for Redeven

A third-party [Redeven](https://github.com/floegence/redeven) service template for the official [Magpie](https://usemagpie.ai/) model gateway and web UI. It runs on an environment with Docker on Linux AMD64 or ARM64, including Docker Desktop on a supported Mac. It runs a separate Magpie instance; it does not adopt or import your desktop app's data.

## Deploy

1. In Redeven, open **Web Services** and choose **Import from GitHub**. Paste `https://github.com/jianyintang/magpie-in-redeven` and select **Magpie**.
2. Deploy the template. For **Web admin key**, use a new random secret, such as the output of `openssl rand -hex 16`. Keep it in a password manager. It is not a model API key.
3. Choose **Open** on the deployed service. Enter the same admin key on Magpie's sign-in page, then configure a provider in Magpie.

The web UI and model API share one container port (`3430`). Redeven assigns a local port and binds it to `127.0.0.1` on the environment host. The container's private gateway listener is not published. Providers, keys, sign-ins and usage live in the instance's managed `/config` volume; a stop, restart, or rebuild that retains the volume preserves them. Back up the volume securely before removing it.

## Connect Flower

In Magpie's **Gateway** settings, create a dedicated **Gateway key**. In Flower on the same environment, add an **OpenAI-compatible** provider with Base URL `http://127.0.0.1:<assigned-port>/v1` and that Gateway key as the API key. Use the local port from the instance details, not the protected browser URL. Configure another client only if its runtime can reach an authorized API endpoint; `127.0.0.1` always refers to the machine the client runs on.

## Maintenance

See the [upstream Docker guide](https://usemagpie.ai/docs/docker) for provider sign-in, gateway keys, and container limitations. Treat the web admin key as full control of the instance. Do not publish the admin port or share the container's raw startup logs, which can contain the admin sign-in URL.

The template is in [`templates/magpie`](templates/magpie). To validate it against the published template SDK:

```sh
go run github.com/floegence/redeven-service-templates/cmd/validate-template@v0.8.2 --current ./templates/magpie
```

The [Sync Magpie Template workflow](https://github.com/jianyintang/magpie-in-redeven/actions/workflows/sync-magpie.yml) checks the [latest official GitHub release](https://github.com/yetone/magpie-releases/releases/latest) once a day at 21:17 UTC. Only a newer non-prerelease version with confirmed `linux/amd64` and `linux/arm64` images at its exact GHCR version tag is eligible. The workflow pins both digests, increments the template `revision`, and publishes to `main` after validation. Failed checks leave the published revision in place; the next scheduled run tries again. If the digests change under a version already pinned, review the change manually.

Use **Run workflow** on `main` to check outside the daily schedule. The manual run defaults to **dry run** and validates without pushing. Redeven's marketplace picks up the revision during its own indexing cycle. Existing deployments are not changed or restarted.

For manual template changes, update both architecture digests and the recommended version together when changing releases. Increment the template `revision` on every change inside its directory.

The template icon is Magpie's [upstream web favicon](https://github.com/yetone/magpie/blob/95e6a4180866afde186e0f1a25369388c7fd7e7f/internal/gui/assets/icons/favicon.svg), with its MIT license notice embedded in the SVG.
