.PHONY: install chat feishu test

install:
	@bash install.sh

chat:
	@hermit chat

feishu:
	@hermit serve --adapter feishu

test:
	@uv run pytest
