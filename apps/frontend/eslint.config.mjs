// Flat config. Next 16 removed `next lint`, and eslint-config-next v16 ships
// flat-config arrays only — it cannot be loaded through the eslintrc compat
// layer (the plugins object is circular, which the eslintrc validator cannot
// serialise). The rule sets are the same two the old .eslintrc.json extended,
// so findings stay comparable across the migration.
import coreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

export default [
  // Flat config does not read .eslintignore.
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "next-env.d.ts",
      "test-results/**",
      "playwright-report/**",
      "coverage/**",
    ],
  },
  ...coreWebVitals,
  ...nextTypescript,
];
