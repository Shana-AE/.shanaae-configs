# ShanaAE Configs (Central Repository)

This is the central configuration hub for the ShanaAE development environment. It serves as the "Source of Truth" for all skills, user rules, and MCP configurations.

## Deployment Links

### MCP Configuration (`ai/mcp/trae.json`)

- **Linux (Remote)**: Symlink to `~/.trae-server/data/Machine/mcp.json`
- **Windows**: Symlink to `C:\Users\shana\AppData\Roaming\Trae\User\mcp.json`

### Trae Configuration

- **Skills**: `.trae/skills` -> `ai/skills`
- **User Rules**: `.trae/user_rules` -> `ai/user_rules`

### Agent Skills Configuration (`.agents`)

This directory is used by the [skills](https://www.npmjs.com/package/skills) CLI tool to manage and store agent skills. It follows the standard structure required by the `skills` package.

- **Skills Location**: `.agents/skills`
- **Usage**: Use `npx skills` to manage these skills.
