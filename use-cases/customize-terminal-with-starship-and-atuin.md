---
title: Customize Your Terminal with Starship and Atuin
slug: customize-terminal-with-starship-and-atuin
description: >-
  Build a productive terminal setup with Starship for a fast, informative
  prompt and Atuin for searchable, synced shell history across machines —
  see git status, Node version, and cloud context at a glance.
skills:
  - starship
  - atuin
category: developer-experience
tags:
  - terminal
  - developer-experience
  - productivity
  - cli
  - tooling
---

# Customize Your Terminal with Starship and Atuin

Erik switches between 5 projects across 3 machines. His default bash prompt shows nothing useful — he runs `git status` constantly, forgets which Node version he needs, and can never find that Docker command he ran last week. Starship gives him an informative prompt that shows git branch, language versions, and cloud context instantly. Atuin replaces shell history with a searchable, synced database across all his machines.

## Step 1: Install Starship

```bash
# Install on any OS
curl -sS https://starship.rs/install.sh | sh

# Add to shell config
# Bash: ~/.bashrc
eval "$(starship init bash)"

# Zsh: ~/.zshrc
eval "$(starship init zsh)"

# Fish: ~/.config/fish/config.fish
starship init fish | source
```

## Step 2: Configure Starship Prompt

```toml
# ~/.config/starship.toml

# Overall format — what shows in the prompt
format = """
$username$hostname$directory$git_branch$git_status$git_state\
$nodejs$python$rust$golang$docker_context\
$kubernetes$aws$terraform\
$cmd_duration$jobs$status\
$line_break$character"""

# Don't show "via" prefix on language modules
[nodejs]
format = "[$symbol($version)]($style) "
symbol = "⬡ "
detect_files = ["package.json", ".node-version"]

[python]
format = "[$symbol($version)]($style) "
symbol = "🐍 "

[rust]
format = "[$symbol($version)]($style) "

[golang]
format = "[$symbol($version)]($style) "

# Git — the most important part
[git_branch]
format = "[$symbol$branch(:$remote_branch)]($style) "
symbol = " "
truncation_length = 30

[git_status]
format = "([$all_status$ahead_behind]($style) )"
conflicted = "⚔️"
ahead = "⇡${count}"
behind = "⇣${count}"
diverged = "⇕⇡${ahead_count}⇣${behind_count}"
untracked = "?${count}"
stashed = "📦"
modified = "!${count}"
staged = "+${count}"
deleted = "✘${count}"

[git_state]
format = '\([$state( $progress_current/$progress_total)]($style)\) '
rebase = "REBASING"
merge = "MERGING"
cherry_pick = "CHERRY-PICKING"

# Directory — show useful path
[directory]
format = "[$path]($style)[$read_only]($read_only_style) "
truncation_length = 3
truncate_to_repo = true
fish_style_pwd_dir_length = 1

# Show command duration if > 2 seconds
[cmd_duration]
min_time = 2_000
format = "[$duration]($style) "
style = "yellow"

# Cloud context
[kubernetes]
format = "[$symbol$context( \\($namespace\\))]($style) "
symbol = "⎈ "
disabled = false
detect_files = ["k8s", "kubernetes"]

[aws]
format = "[$symbol($profile)(\\($region\\))]($style) "
symbol = "☁️ "

[terraform]
format = "[$symbol$workspace]($style) "

[docker_context]
format = "[$symbol$context]($style) "
symbol = "🐳 "
only_with_files = true

# Prompt character
[character]
success_symbol = "[❯](green)"
error_symbol = "[❯](red)"
vimcmd_symbol = "[❮](green)"
```

## Step 3: Install and Configure Atuin

```bash
# Install
curl --proto '=https' --tlsv1.2 -LsSf https://setup.atuin.sh | sh

# Initialize
atuin init zsh >> ~/.zshrc  # or bash/fish

# Register for cross-machine sync (optional)
atuin register -u myusername -e my@email.com -p mypassword
atuin login -u myusername -p mypassword
atuin sync
```

```toml
# ~/.config/atuin/config.toml
[settings]
# Search mode: fuzzy, prefix, fulltext, skim
search_mode = "fuzzy"

# Filter mode: global (all machines), host, session, directory
filter_mode = "global"

# Show command duration and exit status
show_preview = true
show_help = true

# Store in SQLite (local) + sync to Atuin server
db_path = "~/.local/share/atuin/history.db"

# Sync settings
sync_frequency = "5m"
sync_address = "https://api.atuin.sh"

# UI
style = "compact"
inline_height = 20

# Don't record secrets
secrets_filter = true
history_filter = [
  "^export ",
  "^AWS_SECRET",
  "^GITHUB_TOKEN",
  "^PASSWORD=",
]
```

## Step 4: Atuin Usage Patterns

```bash
# Interactive search (replaces Ctrl+R)
# Just press Up arrow or Ctrl+R
# Then type to fuzzy search across ALL history

# Search by directory — find commands you ran in this project
atuin search --cwd .

# Search by time
atuin search --after "2024-01-01" --before "2024-02-01" docker

# Search across machines
atuin search --filter-mode global kubectl

# Stats
atuin stats
# Most used commands, time spent, etc.

# Import existing history
atuin import auto
```

## Step 5: Shell Aliases and Functions

```bash
# ~/.zshrc or ~/.bashrc — useful additions

# Quick project navigation
alias dev="cd ~/dev"
alias dots="cd ~/.dotfiles"

# Git shortcuts that complement Starship's display
alias gs="git status --short"
alias gd="git diff"
alias gl="git log --oneline -20"
alias gp="git push"
alias gc="git commit"

# Docker shortcuts
alias dc="docker compose"
alias dcu="docker compose up -d"
alias dcl="docker compose logs -f"

# Node shortcuts
alias nr="npm run"
alias nrd="npm run dev"
alias nrb="npm run build"

# Quick edit configs
alias zshrc="$EDITOR ~/.zshrc && source ~/.zshrc"
alias starconf="$EDITOR ~/.config/starship.toml"
```

## Summary

Erik's terminal now shows everything he needs at a glance: the git branch with uncommitted changes count, the Node version (detected from `package.json`), the active Kubernetes context, and the AWS profile. He never runs `git status` manually — Starship shows `main +3 !2 ?1` right in the prompt (3 staged, 2 modified, 1 untracked). Atuin replaced his shell history with a fuzzy-searchable database synced across all 3 machines — that Docker command from last week on his work laptop is instantly findable from his home machine. Commands with secrets are automatically filtered out of history. The entire setup is version-controlled in his dotfiles repo and takes 2 minutes to bootstrap on a new machine.
