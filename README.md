# NodalStudio/.github

Organisation-wide configuration for [Nodal Studio](https://nodalstudio.io) on GitHub.

| Path | Role |
|---|---|
| [`profile/README.md`](profile/README.md) | The public profile shown on [github.com/NodalStudio](https://github.com/NodalStudio) |
| `profile/assets/` | Banner, section headers, offer cards, portfolio frames and blog thumbnails |
| [`design/build_assets.py`](design/build_assets.py) | Generates the SVGs and portfolio frames in the brand typefaces |
| [`scripts/update_blog.py`](scripts/update_blog.py) | Refreshes the blog section from the website's RSS feed |
| [`.github/workflows/update-blog.yml`](.github/workflows/update-blog.yml) | Runs the blog refresh daily, on demand, or on a `blog-published` dispatch |
| `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `SECURITY.md`, `SUPPORT.md`, `.github/ISSUE_TEMPLATE/`, `.github/PULL_REQUEST_TEMPLATE.md` | Default community health files for every repository of the organisation that does not define its own |

## The blog section

The block between the `BLOG-STATS`, `BLOG` and `TAGS` markers of `profile/README.md` is
generated — do not edit it by hand. To refresh it locally:

```bash
pip install pillow
python scripts/update_blog.py
```

The workflow can also be triggered right after a website deploy:

```bash
gh api repos/NodalStudio/.github/dispatches -f event_type=blog-published
```

## The visual assets

Text in the SVGs is set in the brand typefaces (Cabinet Grotesk, General Sans) and converted
to paths, so it renders identically everywhere without shipping the fonts. To rebuild after
changing copy or portfolio screenshots, point the script at the website repository:

```bash
pip install fonttools brotli uharfbuzz pillow
python design/build_assets.py --fonts ../NodalWebsite/public/fonts --work ../NodalWebsite/public/work
```

Every asset exists in a `-light` and a `-dark` variant, selected with `<picture>` according
to the reader's GitHub theme.
