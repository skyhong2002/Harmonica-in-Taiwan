# GitHub Pages Deployment

This repository keeps source code and source registries on `main`, and publishes
the generated static site from `site/` to the `gh-pages` branch.

## Branch Roles

- `main`: source files, scripts, registries, templates, and automation config.
- `gh-pages`: generated deployment output only. This branch is updated by
  `scripts/publish_github_pages.py` and should not be edited by hand.

## Local Publisher

Manual publish:

```bash
python3 scripts/publish_github_pages.py
```

Dry local publish without pushing:

```bash
python3 scripts/publish_github_pages.py --no-push
```

The publisher copies `site/` to a sibling deployment worktree at:

```text
/Users/skyhong/Documents/Harmonica-in-Taiwan-gh-pages
```

It writes these Pages-specific root files on `gh-pages`:

- `.nojekyll`
- `CNAME` with `harmonica.observe.tw`

## Scheduled Publish

The LaunchAgent runs:

```bash
python3 scripts/run_pipeline.py --publish-pages
```

Publishing happens only after the pipeline rebuilds the public data and passes
`scripts/validate_public_outputs.py`.

## GitHub Pages Settings

Repository settings should use:

- Source: `Deploy from a branch`
- Branch: `gh-pages`
- Folder: `/ (root)`
- Custom domain: `harmonica.observe.tw`
- Enforce HTTPS: enabled after GitHub finishes certificate provisioning

## Cloudflare DNS

For the current custom subdomain `harmonica.observe.tw`, use one DNS record:

```text
Type: CNAME
Name: harmonica
Target: skyhong2002.github.io
Proxy status: DNS only during initial GitHub Pages verification
TTL: Auto
```

Do not point this subdomain to `skyhong2002.github.io/Harmonica-in-Taiwan` or
to the old machine IP. GitHub Pages expects the CNAME target to exclude the
repository name.

After GitHub Pages is serving HTTPS correctly, Cloudflare can usually remain
`DNS only`. If proxying is re-enabled later, keep Cloudflare SSL/TLS mode at
`Full` or stricter and re-test redirects and feeds.

## Cutover Order

1. Push `gh-pages` with a `CNAME` file.
2. Configure GitHub Pages to publish from `gh-pages` root and set the custom
   domain to `harmonica.observe.tw`.
3. Change Cloudflare DNS from the current machine record to the CNAME above.
4. Wait for DNS and Pages certificate provisioning.
5. Verify:

```bash
dig harmonica.observe.tw +short
curl -I https://harmonica.observe.tw/
curl -fsS https://harmonica.observe.tw/api/latest.json | python3 -m json.tool | head
```

DNS propagation and HTTPS certificate availability can take time; GitHub's docs
say DNS changes can take up to 24 hours.
