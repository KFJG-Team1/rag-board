/**
 * @name PR impact symbol definitions
 * @description Emits Python class and function definitions as PR Collision Atlas symbol records.
 * @kind problem
 * @id pr-impact/symbol-definitions
 * @problem.severity recommendation
 * @precision high
 * @tags maintainability
 */

import python

from Function f
select f,
  "pr_atlas:{\"record_type\":\"symbol_definition\",\"symbol_kind\":\"function\",\"symbol_name\":\"" +
    f.getQualifiedName() +
    "\",\"symbol_key\":\"codeql:symbol:" +
    f.getLocation().getFile().getRelativePath() +
    ":" +
    f.getQualifiedName() +
    "\"}"
