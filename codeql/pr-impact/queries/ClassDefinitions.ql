/**
 * @name PR impact class definitions
 * @description Emits Python class definitions as PR Collision Atlas symbol records.
 * @kind problem
 * @id pr-impact/class-definitions
 * @problem.severity recommendation
 * @precision high
 * @tags maintainability
 */

import python

from Class c
select c,
  "pr_atlas:{\"record_type\":\"symbol_definition\",\"symbol_kind\":\"class\",\"symbol_name\":\"" +
    c.getQualifiedName() +
    "\",\"symbol_key\":\"codeql:symbol:" +
    c.getLocation().getFile().getRelativePath() +
    ":" +
    c.getQualifiedName() +
    "\"}"
