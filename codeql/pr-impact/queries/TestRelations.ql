/**
 * @name PR impact test relation candidates
 * @description Emits functions located in test files as test relation candidates.
 * @kind problem
 * @id pr-impact/test-relations
 * @problem.severity recommendation
 * @precision medium
 * @tags maintainability
 */

import python

from Function f
where f.getLocation().getFile().getRelativePath().regexpMatch(".*test.*\\.py") or
  f.getLocation().getFile().getRelativePath().regexpMatch("tests/.*")
select f,
  "pr_atlas:{\"record_type\":\"static_impact\",\"finding_type\":\"test_relation\",\"confidence\":0.7,\"end_symbol_key\":\"codeql:test:" +
    f.getQualifiedName() +
    "\",\"impact_path\":[\"codeql:test:" +
    f.getQualifiedName() +
    "\"],\"affected_paths\":[\"" +
    f.getLocation().getFile().getRelativePath() +
    "\"],\"related_tests\":[\"test:" +
    f.getLocation().getFile().getRelativePath() +
    "::" +
    f.getName() +
    "\"]}"
