# Gmail to Telegram Code Forwarder

A simple, efficient, and containerized service that monitors a Gmail inbox for new emails from a specific sender, extracts a verification code using a regular expression, and forwards it to a designated Telegram chat.

This script uses the IMAP IDLE protocol for near-instant notifications without constant polling, making it lightweight and responsive.

## Features

-   **Docker-Ready**: Runs as a lightweight, non-root container using `docker-compose`.
-   **IMAP IDLE Support**: Receives new emails instantly without frequent polling.
-   **Secure Configuration**: All secrets and settings are managed via a `.env` file.
-   **Robust Error Handling**: Graceful shutdown on `SIGINT`/`SIGTERM`, and automatic reconnection with exponential backoff for network errors.
-   **Health Checks**: Includes a built-in health check to ensure the service is running correctly, perfect for container orchestrators.
-   **Customizable**: Easily change the sender, code format (regex), and target IMAP folder.
-   **Safe by Default**: Does not mark emails as read unless explicitly configured to do so.

## Quick Start (Ubuntu)

1.  **Clone or Copy Files**: Place all the project files (`Dockerfile`, `docker-compose.yml`, `app/` directory, etc.) onto your server.

2.  **Create `.env` File**: This file will store your secrets.
    ```bash
    touch .env
    nano .env
    ```
    Populate it with the following content.

    ```ini
    # Gmail credentials (use an App Password if 2FA is enabled)
    GMAIL_EMAIL=your_email@gmail.com
    GMAIL_PASSWORD=your_gmail_app_password

    # Telegram Bot credentials
    BOT_TOKEN=your_telegram_bot_token
    CHAT_ID=your_numeric_telegram_chat_id

    # Email sender
    ALLOWED_SENDER=sender@example.com
    ```

3.  **Build and Run the Container**:
    ```bash
    docker compose up -d --build
    ```

4.  **Check Logs**: To confirm everything is running smoothly, view the container's logs.
    ```bash
    docker compose logs -f
    ```
    You should see messages indicating a successful IMAP connection.

## Environment Variables

The service is configured entirely through environment variables defined in the `.env` file.

| Name | Default | Description |
| :--- | :--- | :--- |
| `GMAIL_EMAIL` | — | **Required.** The Gmail address to log into. |
| `GMAIL_PASSWORD` | — | **Required.** The password for the Gmail account. **Use an App Password** if 2FA is enabled. |
| `BOT_TOKEN` | — | **Required.** The token for your Telegram bot. |
| `CHAT_ID` | — | **Required.** The numeric ID of the user, channel, or group to send the code to. |
| `ALLOWED_SENDER` | — | **Required.** The exact email address of the sender to monitor. Emails from others are ignored. |

## Important Notes

*   **Gmail App Password**: If you have 2-Factor Authentication (2FA) enabled on your Google account, you **must** generate an "App Password" for this service. Using your regular password will not work.
*   **Customizing the Regex**: To capture different code formats, modify `REGEX_CODE`. For example, to find an 8-character alphanumeric code prefixed with "Code: ", you could use `(?i)Code:\s*([A-Z0-9]{8})`.
*   **Email Deletion**: This service **does not delete** emails. It only reads them and can optionally mark them as seen.

## Common Docker Commands

-   **Stop the service**:
    ```bash
    docker compose down
    ```
-   **Restart the service**:
    ```bash
    docker compose restart
    ```
-   **Rebuild the image after code changes**:
    ```bash
    docker compose up -d --build
    ```
-   **Check the health status**:
    ```bash
    docker inspect --format='{{json .State.Health}}' kinopub-parser | jq
    ```

## Security

*   **Secrets**: All sensitive credentials are kept in the `.env` file, which is included in `.gitignore` to prevent it from being committed to version control.
*   **Non-Root Container**: The Docker container runs under a dedicated, unprivileged `app` user for improved security.
