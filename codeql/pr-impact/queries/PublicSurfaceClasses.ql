/**
 * @name PR impact public surface classes
 * @description Emits classes defined in __init__.py modules as public surface evidence.
 * @kind problem
 * @id pr-impact/public-surface-classes
 * @problem.severity recommendation
 * @precision medium
 * @tags maintainability
 */

import python

from Class c
where c.getLocation().getFile().getRelativePath().regexpMatch(".*/__init__\\.py") or
  c.getLocation().getFile().getRelativePath() = "__init__.py"
select c,
  "pr_atlas:{\"record_type\":\"static_impact\",\"finding_type\":\"public_surface\",\"confidence\":0.8,\"start_symbol_key\":\"codeql:symbol:" +
    c.getLocation().getFile().getRelativePath() +
    ":" +
    c.getQualifiedName() +
    "\",\"end_symbol_key\":\"codeql:public_api:" +
    c.getQualifiedName() +
    "\",\"impact_path\":[\"codeql:symbol:" +
    c.getLocation().getFile().getRelativePath() +
    ":" +
    c.getQualifiedName() +
    "\",\"codeql:public_api:" +
    c.getQualifiedName() +
    "\"],\"affected_paths\":[\"" +
    c.getLocation().getFile().getRelativePath() +
    "\"]}"
