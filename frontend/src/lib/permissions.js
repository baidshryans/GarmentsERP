// Pure, framework-free permission helpers. Kept separate from the React context
// so they can be unit-tested without a provider.

/**
 * Build a canAccess(moduleLabel, verb) predicate from a permission snapshot.
 * - Superuser: always true.
 * - Not loaded yet: true (avoids flash-hiding tiles during the fetch).
 * - Otherwise: true only if the verb is granted on that module.
 */
export function makeCanAccess({ loaded, is_superuser, modules }) {
  return function canAccess(moduleLabel, verb = "list") {
    if (is_superuser) return true;
    if (!loaded) return true;
    return Boolean(modules?.[moduleLabel]?.[verb]);
  };
}

/**
 * Filter a nav item list against canAccess.
 * - Items with no `module` tag are always kept.
 * - Tagged leaf items are kept only when canAccess(module, perm ?? "list") passes.
 * - Parent items (with nested `items`) are filtered recursively and dropped
 *   when no children survive.
 */
export function filterNavItems(items, canAccess) {
  const out = [];
  for (const item of items) {
    if (item.items && item.items.length > 0) {
      const children = filterNavItems(item.items, canAccess);
      if (children.length > 0) out.push({ ...item, items: children });
      continue;
    }
    if (!item.module || canAccess(item.module, item.perm ?? "list")) {
      out.push(item);
    }
  }
  return out;
}
