# Save to Eudic

When the user asks to save words to Eudic (欧路词典):

1. **Identify Words**: Extract the list of English words to be saved from the context.
2. **Check Token**: Verify if `EUDIC_TOKEN` is set in the environment.
    - If not, ask the user to provide it or set it via `export EUDIC_TOKEN='...'`.
    - Tell the user they can get the token from: <https://my.eudic.net/OpenAPI/Authorization>
