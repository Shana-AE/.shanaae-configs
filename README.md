# ShanaAE Configs (Central Repository)

This is the central configuration hub for the ShanaAE development environment. It serves as the "Source of Truth" for all skills, user rules, and MCP configurations, which are then consumed by the runtime environment (`.trae`).

## Directory Structure

### 📂 `skills/`
Contains the complete collection of available skills, aggregating both custom implementations and installed packages.
*   **Custom Skills**: A comprehensive set of Eudic dictionary tools (`eudic-add-word`, `eudic-get-words`, etc.) for language learning workflows.
*   **NPM Skills (Symlinked)**: Skills installed via NPM packages [skills](https://www.npmjs.com/package/skills) (e.g., `find-skills`, `skill-creator`) are linked here from the `.agents` workspace.

### 📂 `user_rules/`
Defines personal operating rules and preferences in Markdown format.

### 📂 `mcp/`
Configuration for Model Context Protocol (MCP) servers.
*   `trae.json`: Main MCP configuration file.
