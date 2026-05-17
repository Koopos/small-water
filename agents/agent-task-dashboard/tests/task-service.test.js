const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const test = require('node:test');

function loadTaskService(mocks) {
  const filename = path.join(__dirname, '..', 'src', 'lib', 'task-service.ts');
  const source = fs.readFileSync(filename, 'utf8');
  const compiled = ts.transpileModule(source, {
    fileName: filename,
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2019,
      esModuleInterop: true,
    },
  }).outputText;

  const module = { exports: {} };
  const customRequire = (specifier) => {
    if (specifier in mocks) return mocks[specifier];
    return require(specifier);
  };

  const sandbox = {
    module,
    exports: module.exports,
    require: customRequire,
    __filename: filename,
    __dirname: path.dirname(filename),
    process,
    console,
    Buffer,
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
  };

  vm.runInNewContext(compiled, sandbox, { filename });
  return module.exports;
}

function createMocks() {
  const prisma = {
    task: {
      findUnique: async () => null,
      update: async () => null,
    },
    runLog: {
      create: async () => null,
    },
    $transaction: async (operations) => Promise.all(operations),
  };

  const redis = {
    del: async () => undefined,
  };

  return { prisma, redis };
}

test('completeTask writes a run log entry', async () => {
  const mocks = createMocks();
  const task = {
    id: 'task-1',
    projectId: 'project-1',
    lockedBy: 'worker-1',
    workerPool: 'code',
  };
  mocks.prisma.task.findUnique = async () => task;
  let taskUpdateArgs = null;
  mocks.prisma.task.update = async (args) => {
    taskUpdateArgs = args;
    return args;
  };
  let runLogArgs = null;
  mocks.prisma.runLog.create = async (args) => {
    runLogArgs = args;
    return args;
  };

  const { completeTask } = loadTaskService({
    '@/lib/prisma': { prisma: mocks.prisma },
    '@/lib/redis': { getRedis: async () => mocks.redis },
    '@/lib/task-routing': { getWorkerPoolForType: () => 'content', queueScore: () => 0, WORKER_POOLS: ['code', 'image', 'content'] },
    nanoid: { nanoid: () => 'run-123' },
  });

  await completeTask('task-1', 'worker-1', { summary: 'done', stdout: 'ok', branch: 'agent-dev/task-1-abc', github_commit_sha: 'abc1234' });

  assert.ok(taskUpdateArgs);
  assert.equal(taskUpdateArgs.data.branch, 'agent-dev/task-1-abc');
  assert.equal(taskUpdateArgs.data.githubCommitSha, 'abc1234');
  assert.ok(runLogArgs);
  assert.equal(runLogArgs.data.taskId, 'task-1');
  assert.equal(runLogArgs.data.projectId, 'project-1');
  assert.equal(runLogArgs.data.runId, 'run-123');
  assert.equal(runLogArgs.data.status, 'completed');
  assert.equal(runLogArgs.data.stdout, 'ok');
  assert.equal(runLogArgs.data.stderr, null);
});

test('failTask writes a run log entry', async () => {
  const mocks = createMocks();
  const task = {
    id: 'task-2',
    projectId: 'project-2',
    lockedBy: 'worker-2',
    workerPool: 'code',
  };
  mocks.prisma.task.findUnique = async () => task;
  mocks.prisma.task.update = async (args) => args;
  let runLogArgs = null;
  mocks.prisma.runLog.create = async (args) => {
    runLogArgs = args;
    return args;
  };

  const { failTask } = loadTaskService({
    '@/lib/prisma': { prisma: mocks.prisma },
    '@/lib/redis': { getRedis: async () => mocks.redis },
    '@/lib/task-routing': { getWorkerPoolForType: () => 'content', queueScore: () => 0, WORKER_POOLS: ['code', 'image', 'content'] },
    nanoid: { nanoid: () => 'run-456' },
  });

  await failTask('task-2', 'worker-2', 'boom', { stdout: 'partial' });

  assert.ok(runLogArgs);
  assert.equal(runLogArgs.data.taskId, 'task-2');
  assert.equal(runLogArgs.data.projectId, 'project-2');
  assert.equal(runLogArgs.data.runId, 'run-456');
  assert.equal(runLogArgs.data.status, 'failed');
  assert.equal(runLogArgs.data.stdout, 'partial');
  assert.equal(runLogArgs.data.stderr, 'boom');
});
