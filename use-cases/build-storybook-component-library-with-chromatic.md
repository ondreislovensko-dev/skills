---
title: Build a Storybook Component Library with Chromatic Testing
slug: build-storybook-component-library-with-chromatic
description: >-
  Build an interactive component library with Storybook, add visual regression
  testing with Chromatic, document component APIs with autodocs, and publish
  as a shared design system for your team.
skills:
  - storybook
  - chromatic
  - tailwindcss
  - vitest
  - github-actions
category: developer-experience
tags:
  - component-library
  - storybook
  - visual-testing
  - design-system
  - documentation
---

# Build a Storybook Component Library with Chromatic Testing

Lea's team has 200+ React components but no documentation. New developers guess at props by reading source code. Designers can't see available components without running the app. And CSS changes break layouts in unexpected places — nobody catches visual regressions until production. She wants an interactive component catalog, visual regression testing, and auto-generated documentation.

## Step 1: Initialize Storybook

```bash
npx storybook@latest init
npm install -D @storybook/addon-a11y @storybook/test
```

```typescript
// .storybook/main.ts
import type { StorybookConfig } from "@storybook/react-vite";

const config: StorybookConfig = {
  stories: ["../src/**/*.stories.@(ts|tsx)"],
  addons: [
    "@storybook/addon-essentials",
    "@storybook/addon-a11y",
    "@storybook/addon-interactions",
  ],
  framework: "@storybook/react-vite",
  docs: { autodocs: "tag" },
};
export default config;
```

## Step 2: Write Component Stories

```tsx
// src/components/Button/Button.stories.tsx
import type { Meta, StoryObj } from "@storybook/react";
import { fn, expect, userEvent, within } from "@storybook/test";
import { Button } from "./Button";

const meta: Meta<typeof Button> = {
  title: "Components/Button",
  component: Button,
  tags: ["autodocs"],
  parameters: {
    layout: "centered",
    docs: {
      description: {
        component: "Primary UI button component with multiple variants and sizes.",
      },
    },
  },
  argTypes: {
    variant: {
      control: "select",
      options: ["primary", "secondary", "ghost", "danger"],
      description: "Visual style variant",
    },
    size: {
      control: "radio",
      options: ["sm", "md", "lg"],
    },
    loading: { control: "boolean" },
    disabled: { control: "boolean" },
  },
  args: {
    onClick: fn(),
    children: "Click me",
  },
};
export default meta;
type Story = StoryObj<typeof meta>;

export const Primary: Story = {
  args: { variant: "primary" },
};

export const Secondary: Story = {
  args: { variant: "secondary" },
};

export const AllVariants: Story = {
  render: () => (
    <div className="flex gap-3 items-center">
      <Button variant="primary">Primary</Button>
      <Button variant="secondary">Secondary</Button>
      <Button variant="ghost">Ghost</Button>
      <Button variant="danger">Danger</Button>
    </div>
  ),
};

export const AllSizes: Story = {
  render: () => (
    <div className="flex gap-3 items-end">
      <Button size="sm">Small</Button>
      <Button size="md">Medium</Button>
      <Button size="lg">Large</Button>
    </div>
  ),
};

export const Loading: Story = {
  args: { loading: true, children: "Saving..." },
};

// Interaction test — runs in Storybook and CI
export const ClickTest: Story = {
  args: { children: "Submit" },
  play: async ({ canvasElement, args }) => {
    const canvas = within(canvasElement);
    const button = canvas.getByRole("button");
    await userEvent.click(button);
    await expect(args.onClick).toHaveBeenCalledOnce();
  },
};
```

## Step 3: Add Chromatic for Visual Regression Testing

```bash
npm install -D chromatic
```

```yaml
# .github/workflows/chromatic.yml
name: Visual Tests
on: pull_request

jobs:
  chromatic:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
      - run: npm ci

      - name: Run Chromatic
        uses: chromaui/action@latest
        with:
          projectToken: ${{ secrets.CHROMATIC_PROJECT_TOKEN }}
          exitZeroOnChanges: true  # Don't fail, just flag changes for review
          autoAcceptChanges: main  # Auto-accept on main branch
```

## Step 4: Complex Component Story with Mock Data

```tsx
// src/components/DataTable/DataTable.stories.tsx
import type { Meta, StoryObj } from "@storybook/react";
import { DataTable } from "./DataTable";

const mockUsers = Array.from({ length: 20 }, (_, i) => ({
  id: `user_${i}`,
  name: `User ${i + 1}`,
  email: `user${i + 1}@example.com`,
  role: i % 3 === 0 ? "admin" : i % 3 === 1 ? "editor" : "viewer",
  lastActive: new Date(Date.now() - i * 86400000).toISOString(),
  status: i % 5 === 0 ? "inactive" : "active",
}));

const meta: Meta<typeof DataTable> = {
  title: "Components/DataTable",
  component: DataTable,
  tags: ["autodocs"],
  parameters: { layout: "padded" },
};
export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    data: mockUsers,
    columns: [
      { key: "name", header: "Name", sortable: true },
      { key: "email", header: "Email" },
      { key: "role", header: "Role", filterable: true },
      { key: "status", header: "Status" },
    ],
    pageSize: 10,
  },
};

export const Empty: Story = {
  args: {
    data: [],
    columns: [{ key: "name", header: "Name" }],
    emptyMessage: "No users found. Try adjusting your filters.",
  },
};

export const Loading: Story = {
  args: {
    ...Default.args,
    loading: true,
  },
};
```

## Step 5: Publish as a Static Site

```json
// package.json
{
  "scripts": {
    "storybook": "storybook dev -p 6006",
    "build-storybook": "storybook build -o docs-static",
    "test-storybook": "test-storybook"
  }
}
```

```bash
# Build and deploy to any static host
npm run build-storybook
# Output in docs-static/ — deploy to Vercel, Netlify, or GitHub Pages
```

## Summary

Lea's team now has a living component catalog at `design.company.com`. New developers browse components, try different props in the interactive controls, and copy usage examples. Chromatic catches visual regressions on every PR — if a CSS change shifts a button by 2 pixels, the PR shows a visual diff for review. Interaction tests verify that components behave correctly (clicks, keyboard navigation, form submission). The autodocs feature generates API documentation from TypeScript types and JSDoc comments. Designers review the Storybook directly and leave comments on specific component states.
