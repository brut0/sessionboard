import createClient from 'openapi-fetch';
import type { paths, components } from './schema';

const getBaseUrl = (): string => {
  if (typeof process !== 'undefined' && process.env.NODE_ENV === 'test') {
    return 'http://localhost:8000';
  }
  return '';
};

export const apiClient = createClient<paths>({
  baseUrl: getBaseUrl(),
});

export type Specialist = components['schemas']['Specialist'];
export type SpecialistCreate = components['schemas']['SpecialistCreate'];
export type Client = components['schemas']['Client'];
export type ClientCreate = components['schemas']['ClientCreate'];
export type Room = components['schemas']['Room'];
export type RoomCreate = components['schemas']['RoomCreate'];
export type Session = components['schemas']['Session'];
export type SessionCreate = components['schemas']['SessionCreate'];
export type SessionStatus = components['schemas']['SessionStatus'];
export type SessionStatusUpdate = components['schemas']['SessionStatusUpdate'];
export type ConflictItem = components['schemas']['ConflictItem'];
export type ConflictError = components['schemas']['ConflictError'];
export type ErrorDetail = components['schemas']['ErrorDetail'];
