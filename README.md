# MCP Weather Service

## Overview

This repository contains a simple MCP server for a weather application built with Gradio. The main application is implemented in `gradio_server.py` and exposes weather tools via an MCP server using the `mcp` framework.

The UI is built with Gradio so you can run the service locally and interact with it in a browser. VS Code is the recommended development client for editing the code, inspecting `pyproject 2.toml`, and launching the server.

## Project Structure

- `gradio_server.py` - Main entrypoint for the weather MCP server and Gradio UI.
- `pyproject 2.toml` - Python project metadata and dependency declarations.
- `README.md` - Project documentation.
- `.vscode/` - VS Code workspace settings (if present).
- `.git/` - Git repository metadata.

## What this service does

- Runs an MCP server with `FastMCP` from `mcp.server.fastmcp`.
- Provides weather forecast capabilities for U.S. coordinates via the NOAA/NWS API.
- Provides global weather data using the Open-Meteo API.
- Uses OpenStreetMap Nominatim geocoding to resolve place names into latitude/longitude.
- Exposes a Gradio web UI with tabs for:
  - Forecast by latitude/longitude
  - U.S. weather alerts by state
  - Weather by place name
  - Natural-language weather questions

## Dependencies

The current dependency list in `pyproject 2.toml` includes:

- `gradio[mcp]>=6.11.0`
- `httpx>=0.28.1`
- `mcp[cli]>=1.26.0`

## Setup

1. Open the repository in VS Code.
2. Create and activate a Python environment targeting Python 3.11 or newer.
3. Install the dependencies:

```bash
python -m pip install "gradio[mcp]>=6.11.0" httpx mcp[cli]
```

> If you prefer, install from `pyproject 2.toml` with a tool that supports PEP 621 and its custom file name.

## Running the app

Run the Gradio server with:

```bash
python gradio_server.py
```

Then open the browser at:

- `http://localhost:7860`

The server listens on `0.0.0.0:7860` by default.

## Development notes

- The application prints `✅ Global Weather MCP Server is running...` when the MCP instance starts.
- U.S. forecast and alert tools use the National Weather Service API.
- Global forecasts use Open-Meteo and perform weather-code mapping for human-friendly output.
- Natural-language questions are parsed to extract place names and return a weather summary.

## Notes

- The current implementation uses direct API calls and does not include persistent caching.
- U.S. alerts are limited to the `alerts/active` API and require a two-letter state code.
- Gradio provides the UI, while MCP tools can be extended for integrations or chat clients in the future.
