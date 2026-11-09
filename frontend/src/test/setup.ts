import '@testing-library/jest-dom';
import { afterEach, afterAll } from 'vitest';
import { server } from './mocks/server';

server.listen({ onUnhandledRequest: 'error' });

afterEach(() => server.resetHandlers());
afterAll(() => server.close());
