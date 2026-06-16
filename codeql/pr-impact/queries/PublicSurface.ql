/**
 * @name PR impact public surface
 * @description Emits symbols defined in __init__.py modules as public surface evidence.
 * @kind problem
 * @id pr-impact/public-surface
 * @problem.severity recommendation
 * @precision medium
 * @tags maintainability
 */

import python

from Function f
where f.getLocation().getFile().getRelativePath().regexpMatch(".*/__init__\\.py") or
  f.getLocation().getFile().getRelativePath() = "__init__.py"
select f,
  "pr_atlas:{\"record_type\":\"static_impact\",\"finding_type\":\"public_surface\",\"confidence\":0.8,\"start_symbol_key\":\"codeql:symbol:" +
    f.getLocation().getFile().getRelativePath() +
    ":" +
    f.getQualifiedName() +
    "\",\"end_symbol_key\":\"codeql:public_api:" +
    f.getQualifiedName() +
    "\",\"impact_path\":[\"codeql:symbol:" +
    f.getLocation().getFile().getRelativePath() +
    ":" +
    f.getQualifiedName() +
    "\",\"codeql:public_api:" +
    f.getQualifiedName() +
    "\"],\"affected_paths\":[\"" +
    f.getLocation().getFile().getRelativePath() +
    "\"]}"
