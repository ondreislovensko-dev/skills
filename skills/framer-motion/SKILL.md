---
name: framer-motion
description: >-
  Assists with building fluid animations and gestures in React applications using Framer
  Motion. Use when creating enter/exit animations, layout transitions, scroll-triggered
  effects, drag interactions, or orchestrated animation sequences. Trigger words: framer
  motion, motion, animate, spring, layout animation, animatepresence, scroll animation.
license: Apache-2.0
compatibility: "Requires React 18+"
metadata:
  author: terminal-skills
  version: "1.0.0"
  category: design
  tags: ["framer-motion", "animation", "react", "gestures", "transitions"]
---

# Framer Motion

## Overview

Framer Motion is a production-ready animation library for React that provides declarative animations, spring physics, layout transitions, gesture handling, and scroll-driven effects. It enables smooth enter/exit animations via AnimatePresence, shared element transitions with layoutId, and orchestrated sequences with variants and stagger.

## Instructions

- When animating components, use `<motion.div>` with `initial`, `animate`, and `exit` props for declarative mount/unmount animations, choosing `type: "spring"` for interactive elements and `type: "tween"` for loading animations.
- When implementing exit animations, wrap conditionally rendered components with `<AnimatePresence>` and use `mode="wait"` for page transitions where the exit must complete before the enter begins.
- When building layout animations, add the `layout` prop for automatic position and size transitions, and use `layoutId` for shared element morphing between components (like expanding a card to a full page).
- When orchestrating sequences, define `variants` with named states and use `staggerChildren`, `delayChildren`, and `staggerDirection` for coordinated multi-element animations.
- When handling gestures, use `whileHover`, `whileTap`, `whileDrag`, and `whileInView` for gesture-driven animation states, with `drag` and `dragConstraints` for draggable elements.
- When creating scroll animations, use `useScroll()` to track scroll progress and `useTransform()` to map scroll position to animation values like parallax offsets or progress bars.

## Examples

### Example 1: Build a page transition system

**User request:** "Add smooth page transitions to my React app"

**Actions:**
1. Wrap the router outlet with `<AnimatePresence mode="wait">`
2. Add `initial`, `animate`, and `exit` props to each page component with slide and fade
3. Use `variants` with staggered children to animate page content elements sequentially
4. Add a shared header using `layoutId` so it morphs smoothly between pages

**Output:** A React app with smooth slide-and-fade page transitions and staggered content entrance animations.

### Example 2: Create a draggable card stack with reordering

**User request:** "Build a Tinder-like card stack with swipe gestures"

**Actions:**
1. Set up a card stack with `<motion.div drag="x">` and `dragConstraints`
2. Use `useMotionValue()` and `useTransform()` to rotate and fade cards based on drag offset
3. Add `onDragEnd` handler to detect swipe direction and threshold
4. Use `<AnimatePresence>` for exit animation as cards fly off screen

**Output:** An interactive card stack with swipe gestures, rotation effects, and smooth exit animations.

## Guidelines

- Use `spring` type for interactive animations (hover, tap, drag) since they feel more natural than tween.
- Use `tween` with specific `duration` for loading and progress animations where predictable timing matters.
- Always wrap conditional renders with `<AnimatePresence>` to enable exit animations.
- Use `layoutId` for shared element transitions instead of manual position calculations.
- Respect `prefers-reduced-motion` using `useReducedMotion()` to disable or simplify animations.
- Keep UI interaction animations under 300ms to avoid feeling sluggish.
- Use `useTransform()` over `useEffect` for scroll-driven animations since it runs off the main thread.
