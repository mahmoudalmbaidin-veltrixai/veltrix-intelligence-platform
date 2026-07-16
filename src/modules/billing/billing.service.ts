/**
 * Billing service (mock). Never simulates real charges.
 * INTEGRATION POINT: /api/v1/billing/{plans,invoices,payment-method,usage}
 * permission: billing:read / billing:manage
 */
import { latency, isoAgo } from '@/shared/lib/mock'

export interface Plan { key: string; name: string; price: number; features: string[]; current: boolean }
export interface Invoice { id: string; number: string; date: string; amount: number; status: 'paid' | 'due' | 'overdue' }
export interface PaymentMethod { brand: string; last4: string; expiry: string }
export interface UsageLine { label: string; used: number; limit: number; unit: string }

const PLANS: Plan[] = [
  { key: 'team', name: 'Team', price: 0, features: ['5 pipelines', '10 dashboards', 'Community support'], current: false },
  { key: 'business', name: 'Business', price: 1200, features: ['100 pipelines', '250 dashboards', 'AI assistant', 'Email support'], current: false },
  { key: 'enterprise', name: 'Enterprise', price: 4800, features: ['Unlimited pipelines & dashboards', 'AI agents & automation', 'SSO & advanced governance', 'Dedicated support'], current: true },
]
const INVOICES: Invoice[] = [
  { id: 'inv_1', number: 'VIP-2026-004', date: isoAgo(60 * 24 * 5), amount: 4800, status: 'paid' },
  { id: 'inv_2', number: 'VIP-2026-003', date: isoAgo(60 * 24 * 35), amount: 4800, status: 'paid' },
  { id: 'inv_3', number: 'VIP-2026-002', date: isoAgo(60 * 24 * 65), amount: 4800, status: 'paid' },
  { id: 'inv_4', number: 'VIP-2026-005', date: isoAgo(60 * 24 * 1), amount: 620, status: 'due' },
]
const USAGE: UsageLine[] = [
  { label: 'Pipelines', used: 42, limit: 500, unit: '' },
  { label: 'Dashboards', used: 128, limit: 1000, unit: '' },
  { label: 'AI agent runs', used: 41, limit: 50, unit: '/mo' },
  { label: 'API calls', used: 862_000, limit: 1_000_000, unit: '/mo' },
  { label: 'Storage', used: 780, limit: 1000, unit: 'GB' },
]

export const billingService = {
  async listPlans() { await latency(); return PLANS.map((p) => ({ ...p })) },
  async listInvoices() { await latency(); return INVOICES.map((i) => ({ ...i })) },
  async getPaymentMethod(): Promise<PaymentMethod> { await latency(); return { brand: 'Visa', last4: '6411', expiry: '08/28' } },
  async getUsage() { await latency(); return USAGE.map((u) => ({ ...u })) },
}
