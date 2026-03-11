.PHONY: install chat feishu menubar menubar-app test

install:
	@bash install.sh

chat:
	@hermit chat

feishu:
	@hermit serve --adapter feishu

menubar:
	@hermit-menubar --adapter feishu

menubar-app:
	@hermit-menubar-install-app --adapter feishu --open

test:
	@uv run pytest
