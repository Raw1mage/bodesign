# integrations/opencms

Optional opencms/opencode integration adapter. It can register fileview or gateway surfaces around the same `/bodesign/` web APIs and MCP tools without making opencms the product boundary.

## Published Web registration

opencms Published Web only shows apps that exist in both the gateway route table and the user registry.

Runtime registration used for the local dev box:

- `~/.config/web_registry.json`: add `entryName: "bodesign"`, `projectRoot: "/home/pkcs12/projects/bodesign"`, `publicBasePath: "/bodesign"`, `host: "127.0.0.1"`, `primaryPort: 8765`, `webctlPath: "/home/pkcs12/projects/bodesign/webctl.sh"`, `enabled: true`, `access: "public"`.
- Gateway route: publish `/bodesign` to `127.0.0.1:8765` via opencode `webctl.sh publish-route /bodesign 127.0.0.1 8765`.

The bodesign upstream supports the preserved `/bodesign/` prefix directly, so the gateway should not strip the prefix.
