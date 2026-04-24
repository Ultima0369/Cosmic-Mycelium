// Commitlint Configuration for Cosmic Mycelium
// Enforces conventional commit format for all commits

module.exports = {
  extends: ['@commitlint/config-conventional'],

  rules: {
    // Type must be one of our conventional types
    'type-enum': [
      2,
      'always',
      [
        'feat',      // New feature
        'fix',       // Bug fix
        'docs',      // Documentation only
        'style',     // Formatting, missing semicolons, etc. (no code change)
        'refactor',  // Code change that neither fixes a bug nor adds a feature
        'perf',      // Performance improvement
        'test',      // Adding or correcting tests
        'build',     // Build system or external dependency changes
        'ci',        // CI configuration changes
        'chore',     // Other changes that don't modify src or test files
        'revert',    // Reverts a previous commit
        'wip',       // Work in progress (allowed on feature branches)
        'hotfix',    // Critical production fix
      ],
    ],

    // Subject case: sentence case (first letter capital)
    'subject-case': [2, 'never', ['sentence-case']],

    // Subject must not end with period
    'subject-full-stop': [2, 'never', '.'],

    // Subject max length
    'subject-max-length': [2, 'always', 72],

    // Header max length
    'header-max-length': [2, 'always', 100],

    // Blank line between header and body
    'body-leading-blank': [2, 'always'],

    // Body max line length
    'body-max-line-length': [2, 'always', 88],

    // Footer max line length
    'footer-max-length': [2, 'always', 88],

    // Body/Footer must not be empty if header is
    'body-empty': [0, 'never'],  // Allow empty body for simple commits
    'footer-empty': [1, 'always'], // Footer required for breaking changes

    // Breaking change indicator
    'breaking-prefix': [2, 'always', 'BREAKING CHANGE:'],

    // Scope is optional but encouraged for complex changes
    'scope-enum': [1, 'always', [
      'hic',          // HIC (本体恒常性) changes
      'sympnet',      // SympNet engine changes
      'slime',        // Slime mold explorer changes
      'myelination',  // Myelination memory changes
      'infant',       // Core infant class
      'cluster',      // Cluster coordination
      'common',       // Shared utilities
      'physics',      // Physics validation layer
      'config',       // Configuration changes
      'deps',         // Dependencies
      'docs',         // Documentation
      'tests',        // Test suite
    ]],

    // References (issue/PR linking)
    'references-empty': [2, 'never'],

    // Allow WIP commits on any branch except main
    'type-case': [0],  // Allow lowercase types
  },

  // Help message for violations
  prompt: {
    messages: {
      type: '选择要提交的变更类型:',
      scope: '选择影响范围 (可选，按回车跳过):',
      subject: '用一句话简明描述变更:',
      body: '提供更详细的描述 (可选):',
      breaking: '是否有破坏性变更? (y/N):',
      footer: '附加信息 (可选，如关联的issue #):',
    },
    choices: {
      type: [
        {value: 'feat', name: 'feat:    新功能 (非破坏性)'},
        {value: 'fix', name: 'fix:      Bug修复'},
        {value: 'docs', name: 'docs:     文档变更'},
        {value: 'style', name: 'style:    代码格式调整 (不影响功能)'},
        {value: 'refactor', name: 'refactor: 代码重构'},
        {value: 'perf', name: 'perf:     性能优化'},
        {value: 'test', name: 'test:     测试相关'},
        {value: 'build', name: 'build:    构建系统或依赖变更'},
        {value: 'ci', name: 'ci:       CI/CD配置变更'},
        {value: 'chore', name: 'chore:    杂项/维护'},
        {value: 'revert', name: 'revert:   回滚提交'},
        {value: 'hotfix', name: 'hotfix:   热修复'},
        {value: 'wip', name: 'wip:      进行中 (暂不合并)'},
      ],
    },
  },
};
