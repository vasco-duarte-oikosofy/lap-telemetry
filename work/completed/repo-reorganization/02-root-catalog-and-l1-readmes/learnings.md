# Learnings: 02-root-catalog-and-l1-readmes

## Notes

- Empty future L1 folders need tracked README files so the intended structure is visible before file moves happen.
- The root catalog should stay high-level; detailed placement rules belong in each folder README and in the repo reorganization spec.
- Running the test suite can touch tracked test-report files. This slice keeps those report diffs out of the commit because the reports are not part of the catalog/README outcome.
