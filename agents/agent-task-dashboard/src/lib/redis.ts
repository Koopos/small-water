type RedisClient = {
  connect(): Promise<void>;
  quit(): Promise<void>;
  on(event: "error", listener: (error: unknown) => void): void;
  zAdd(key: string, members: Array<{ score: number; value: string }>): Promise<number>;
  zRem(key: string, members: string | string[]): Promise<number>;
  zPopMin(key: string, count?: number): Promise<{ value: string; score: number } | Array<{ value: string; score: number }> | null>;
  set(key: string, value: string, options?: { PX?: number }): Promise<unknown>;
  get(key: string): Promise<string | null>;
  del(key: string | string[]): Promise<number>;
};

const globalForRedis = globalThis as unknown as { redis?: RedisClient };

function redisUrl() {
  return process.env.REDIS_URL ?? "redis://127.0.0.1:6379";
}

async function loadRedisModule(): Promise<{ createClient: (options: { url: string }) => RedisClient }> {
  return import("redis") as unknown as Promise<{ createClient: (options: { url: string }) => RedisClient }>;
}

export async function getRedis(): Promise<RedisClient> {
  if (!globalForRedis.redis) {
    const { createClient } = await loadRedisModule();
    const client = createClient({ url: redisUrl() });
    client.on("error", (error) => {
      console.error("Redis error:", error);
    });
    await client.connect();
    globalForRedis.redis = client;
  }
  return globalForRedis.redis;
}

export async function closeRedis() {
  if (globalForRedis.redis) {
    await globalForRedis.redis.quit();
    globalForRedis.redis = undefined;
  }
}
