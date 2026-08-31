# swym-thememate-plugin

A Claude Code plugin bundling **ThemeMate**, a Swym API-aware assistant for
implementing and debugging Swym features (Wishlist Plus, Save For Later,
Back In Stock, Recently Viewed, B2B List). Full pull/edit/local-preview/
push/GitHub workflow on Shopify storefronts. Knowledge-only suggestions on
other platforms (headless via the Swym REST API, BigCommerce, WooCommerce,
Wix) -- no theme pull, edit, or push there.

Who this is for: Agency Partners, Merchants, and Swym Internal staff
(Success, Support, ACQ).

## Prerequisites

**1. Claude Code**
```bash
npm install -g @anthropic-ai/claude-code
claude login
```

**2. Node.js 18+**
```bash
node --version   # must be >= 18.0.0
```

**3. Shopify CLI** (Shopify storefront work only)
```bash
npm install -g @shopify/cli@latest
shopify auth login
```

**4. `gh` CLI** (only if you want GitHub version control on your changes)
```bash
gh auth login
```

**5. A browser-automation MCP server**, for local-preview validation --
either the Playwright MCP or the `chrome-devtools` MCP, whichever your
Claude Code setup already has connected.

## Install

Marketplace: `swym-corp-custom-solutions/swym-thememate-plugin`. Plugin name: `swym`.

### From the Claude Code CLI (terminal)

In an interactive session:
```
/plugin marketplace add swym-corp-custom-solutions/swym-thememate-plugin
/plugin install swym@swym-thememate-plugin
```

Non-interactive (scripting/CI) -- installs to user scope by default:
```bash
claude plugin marketplace add swym-corp-custom-solutions/swym-thememate-plugin
claude plugin install swym@swym-thememate-plugin
```

### From the Claude Desktop app

The desktop app's Code tab has its own plugin browser -- no terminal needed:
1. Click the **+** button next to the prompt box.
2. Select **Plugins > Add plugin** to open the plugin browser.
3. Add the marketplace `swym-corp-custom-solutions/swym-thememate-plugin`.
4. Find **swym** in the list and install it, choosing a scope (user, project, or local).

### By asking Claude directly in chat

In any Claude Code chat (terminal or desktop), you can just ask Claude to do
the steps above for you instead of typing the commands yourself, e.g.:

> Add & install plugin swym-corp-custom-solutions/swym-thememate-plugin

This isn't a special command -- Claude reads the request and runs the same
marketplace-add and install steps on your behalf.

### Cloud sessions (claude.ai/code)

The plugin browser and `/plugin` aren't available in cloud sessions. Add this
to the repository's `.claude/settings.json` instead:
```json
{
  "extraKnownMarketplaces": {
    "swym-thememate-plugin": {
      "source": { "source": "github", "repo": "swym-corp-custom-solutions/swym-thememate-plugin" }
    }
  },
  "enabledPlugins": { "swym@swym-thememate-plugin": true }
}
```

## Usage

Just talk to Claude Code once the plugin is installed -- ThemeMate's
description-based trigger picks it up for Swym feature work. Ask a knowledge
question, describe a bug, or describe something to build; ThemeMate
classifies the mode and platform itself (see
`skills/thememate/SKILL.md`).

Alternatively, activate it directly with the slash command `/swym:thememate`
(plugin skills are namespaced by the plugin name, `swym`). You don't need to
type the full thing -- start typing `/thememate` and the autocomplete
dropdown will surface `/swym:thememate` to select.

For Shopify implementation and debug-with-a-fix work, ThemeMate always
presents a plan and waits for your explicit confirmation before writing or
pushing anything -- see SKILL.md Section 4.

## Structure

```
.claude-plugin/
  plugin.json       # plugin manifest
  marketplace.json  # self-referencing marketplace so this repo is installable on its own
skills/thememate/
  SKILL.md          # entry point: roles, modes, platform routing, the plan-before-edit gate
  references/
    roles.md              # agency / merchant / swym_internal detection
    tools-and-testing.md  # tool choice per mode, local-preview validation order
    shopify-workflow.md   # prerequisites -> pull -> plan -> edit -> preview -> push -> GitHub
    failure-patterns.md   # 9 common post-theme-update Swym failure patterns
    rest-api.md           # Swym REST API (headless)
    js-api.md             # Swym JS API (Shopify/BigCommerce)
    other-platforms.md    # knowledge-only support matrix
```

## Known gaps

Most `NEEDS VERIFICATION` markers in `rest-api.md` have been resolved against
Swym's public developer docs (update-list-attributes and single-product
social-count now have confirmed paths and parameters). Still unconfirmed:

- The exact REST path for merging a guest session into a logged-in one (the
  JS SDK's equivalent, `guest-validate-sync`, is confirmed by name, but the
  raw HTTP path isn't documented).
- Whether a dedicated batch social-count REST endpoint exists at all, versus
  the JS SDK's batch method simply looping the single-product endpoint.
- The Save For Later `remove` method signature and its "Add Items [Beta]"
  REST path.
- The Back In Stock (SBiSA) App Embed block's exact handle -- verify per
  store via the grep in `js-api.md` rather than assuming a name.

Check `developers.getswym.com` (or the Swym Developer Docs MCP, if connected)
before relying on any entry still marked `NEEDS VERIFICATION`.
