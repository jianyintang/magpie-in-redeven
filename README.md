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

Update both architecture digests and the recommended version together. Increment the template `revision` on every change inside its directory.
