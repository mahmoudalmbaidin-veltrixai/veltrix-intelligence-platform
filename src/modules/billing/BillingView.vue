<script setup lang="ts">
import { ref } from 'vue'
import { useQuery } from '@/shared/lib/query'
import { billingService, type Invoice, type UsageLine } from './billing.service'
import { usePlatformStore } from '@/shared/stores/platform'
import { useUiStore } from '@/shared/stores/ui'
import { formatNumber, formatDateTime } from '@/shared/lib/format'
import VipPageHeader from '@/shared/ui/VipPageHeader.vue'
import VipTabs from '@/shared/ui/VipTabs.vue'
import VipCard from '@/shared/ui/VipCard.vue'
import VipButton from '@/shared/ui/VipButton.vue'
import VipBadge from '@/shared/ui/VipBadge.vue'
import VipAlert from '@/shared/ui/VipAlert.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipTable, { type Column } from '@/shared/ui/VipTable.vue'

const platform = usePlatformStore()
const ui = useUiStore()
const tab = ref('overview')
const tabs = [
  { value: 'overview', label: 'Overview' }, { value: 'plans', label: 'Plans' },
  { value: 'usage', label: 'Usage' }, { value: 'invoices', label: 'Invoices' }, { value: 'payment', label: 'Payment' },
]
const { data: plans } = useQuery('billing:plans', () => billingService.listPlans())
const { data: invoices } = useQuery('billing:invoices', () => billingService.listInvoices())
const { data: usage } = useQuery('billing:usage', () => billingService.getUsage())
const { data: pm } = useQuery('billing:pm', () => billingService.getPaymentMethod())

function pct(u: UsageLine) { return Math.min(100, Math.round((u.used / u.limit) * 100)) }
function usageTone(u: UsageLine) { const p = pct(u); return p >= 100 ? 'danger' : p >= 80 ? 'warning' : 'info' }
function planAction(name: string) { ui.pushToast({ kind: 'info', title: `${name}`, message: 'Plan changes and payment are backend-gated — no charge is made here.' }) }

const invColumns: Column<Invoice>[] = [
  { key: 'number', label: 'Invoice' }, { key: 'date', label: 'Date' }, { key: 'amount', label: 'Amount', align: 'right' },
  { key: 'status', label: 'Status' }, { key: 'actions', label: '', align: 'right' },
]
</script>

<template>
  <div>
    <VipPageHeader title="Billing" :description="`${platform.organization.name} · ${platform.organization.plan} plan`" />
    <VipTabs v-model="tab" :tabs="tabs" />
    <div class="bill">
      <!-- OVERVIEW -->
      <template v-if="tab === 'overview'">
        <div class="bill-grid">
          <VipCard>
            <div class="bill-plan-name">Enterprise</div>
            <div class="bill-plan-price">$4,800<span>/mo</span></div>
            <VipBadge tone="success" size="sm">Active subscription</VipBadge>
            <p class="bill-note">Renews monthly · next invoice in 25 days</p>
          </VipCard>
          <VipCard>
            <h3 class="bill-h">Entitlement usage</h3>
            <div v-for="u in (usage ?? []).slice(0, 3)" :key="u.label" class="bill-usage">
              <div class="bill-usage-head"><span>{{ u.label }}</span><span>{{ formatNumber(u.used, { style: 'compact' }) }} / {{ formatNumber(u.limit, { style: 'compact' }) }}</span></div>
              <div class="bill-bar"><div class="bill-bar-fill" :class="`is-${usageTone(u)}`" :style="{ width: `${pct(u)}%` }" /></div>
            </div>
          </VipCard>
        </div>
        <VipAlert tone="info" title="Billing is backend-managed">Plan changes, proration and payments are processed by the billing service. This UI never charges a card.</VipAlert>
      </template>

      <!-- PLANS -->
      <template v-else-if="tab === 'plans'">
        <div class="bill-plans">
          <VipCard v-for="p in plans" :key="p.key" class="bill-planc" :class="{ 'is-current': p.current }">
            <div class="bill-planc-name">{{ p.name }}<VipBadge v-if="p.current" tone="brand" size="sm">Current</VipBadge></div>
            <div class="bill-planc-price">{{ p.price === 0 ? 'Free' : `$${formatNumber(p.price)}` }}<span v-if="p.price">/mo</span></div>
            <ul class="bill-features"><li v-for="f in p.features" :key="f"><VipIcon name="check" :size="13" />{{ f }}</li></ul>
            <VipButton v-if="!p.current" :variant="p.price > 4800 ? 'primary' : 'secondary'" block @click="planAction(p.price > 4800 ? 'Upgrade' : 'Change plan')">{{ p.price > 4800 ? 'Upgrade' : 'Switch' }}</VipButton>
            <VipButton v-else variant="tertiary" block disabled>Your plan</VipButton>
          </VipCard>
        </div>
      </template>

      <!-- USAGE -->
      <template v-else-if="tab === 'usage'">
        <div class="bill-usage-grid">
          <VipCard v-for="u in usage" :key="u.label">
            <div class="bill-usage-head"><span>{{ u.label }}</span><VipBadge :tone="usageTone(u)" size="sm">{{ pct(u) }}%</VipBadge></div>
            <div class="bill-bar"><div class="bill-bar-fill" :class="`is-${usageTone(u)}`" :style="{ width: `${pct(u)}%` }" /></div>
            <div class="bill-usage-nums">{{ formatNumber(u.used) }} / {{ formatNumber(u.limit) }} {{ u.unit }}</div>
          </VipCard>
        </div>
      </template>

      <!-- INVOICES -->
      <template v-else-if="tab === 'invoices'">
        <VipTable :columns="invColumns" :rows="invoices ?? []" :row-key="(r) => r.id">
          <template #cell-date="{ row }">{{ formatDateTime(row.date) }}</template>
          <template #cell-amount="{ row }">{{ formatNumber(row.amount, { style: 'currency', currency: 'USD', decimals: 0 }) }}</template>
          <template #cell-status="{ row }"><VipBadge :tone="row.status === 'paid' ? 'success' : row.status === 'due' ? 'warning' : 'danger'" size="sm">{{ row.status }}</VipBadge></template>
          <template #cell-actions="{ row }"><VipButton variant="ghost" size="xs" icon="download" @click="planAction(`Download ${row.number}`)">PDF</VipButton></template>
        </VipTable>
      </template>

      <!-- PAYMENT -->
      <template v-else>
        <VipCard class="bill-pay">
          <h3 class="bill-h">Payment method</h3>
          <div class="bill-card"><VipIcon name="card" :size="20" /><span>{{ pm?.brand }} ending {{ pm?.last4 }}</span><span class="bill-exp">exp {{ pm?.expiry }}</span></div>
          <VipButton variant="secondary" size="sm" @click="planAction('Update payment method')">Update</VipButton>
          <h3 class="bill-h" style="margin-top:24px">Billing contact & tax</h3>
          <p class="bill-note">Billing contact, VAT / tax ID and address are entered directly by the account owner — this UI does not store payment data.</p>
        </VipCard>
      </template>
    </div>
  </div>
</template>

<style scoped>
.bill { margin-top: var(--vip-sp-7); display: flex; flex-direction: column; gap: var(--vip-sp-6); }
.bill-grid { display: grid; grid-template-columns: 1fr 1.4fr; gap: var(--vip-sp-6); }
.bill-plan-name { font-size: var(--vip-fs-md); color: var(--vip-text-muted); }
.bill-plan-price { font-size: var(--vip-fs-3xl); font-weight: var(--vip-fw-bold); margin: var(--vip-sp-3) 0; }
.bill-plan-price span { font-size: var(--vip-fs-md); color: var(--vip-text-muted); font-weight: var(--vip-fw-regular); }
.bill-note { font-size: var(--vip-fs-sm); color: var(--vip-text-muted); margin-top: var(--vip-sp-4); }
.bill-h { font-size: var(--vip-fs-md); font-weight: var(--vip-fw-semibold); margin-bottom: var(--vip-sp-5); }
.bill-usage { margin-bottom: var(--vip-sp-5); }
.bill-usage-head { display: flex; justify-content: space-between; font-size: var(--vip-fs-sm); color: var(--vip-text-secondary); margin-bottom: var(--vip-sp-3); }
.bill-bar { height: 8px; background: var(--vip-surface-3); border-radius: var(--vip-radius-full); overflow: hidden; }
.bill-bar-fill { height: 100%; border-radius: var(--vip-radius-full); }
.bill-bar-fill.is-info { background: var(--vip-info); }
.bill-bar-fill.is-warning { background: var(--vip-warning); }
.bill-bar-fill.is-danger { background: var(--vip-danger); }
.bill-usage-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: var(--vip-sp-5); }
.bill-usage-nums { font-size: var(--vip-fs-xs); color: var(--vip-text-muted); margin-top: var(--vip-sp-3); font-variant-numeric: tabular-nums; }
.bill-plans { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--vip-sp-6); }
.bill-planc { display: flex; flex-direction: column; }
.bill-planc.is-current { border-color: var(--vip-brand-500); }
.bill-planc-name { display: flex; align-items: center; gap: var(--vip-sp-3); font-size: var(--vip-fs-lg); font-weight: var(--vip-fw-semibold); }
.bill-planc-price { font-size: var(--vip-fs-2xl); font-weight: var(--vip-fw-bold); margin: var(--vip-sp-4) 0; }
.bill-planc-price span { font-size: var(--vip-fs-sm); color: var(--vip-text-muted); font-weight: var(--vip-fw-regular); }
.bill-features { list-style: none; margin: 0 0 var(--vip-sp-6); padding: 0; flex: 1; display: flex; flex-direction: column; gap: var(--vip-sp-3); }
.bill-features li { display: flex; align-items: center; gap: var(--vip-sp-3); font-size: var(--vip-fs-sm); color: var(--vip-text-secondary); }
.bill-features li :deep(.vip-icon) { color: var(--vip-success-text); }
.bill-pay { max-width: 560px; }
.bill-card { display: flex; align-items: center; gap: var(--vip-sp-4); padding: var(--vip-sp-5); background: var(--vip-surface-2); border-radius: var(--vip-radius-md); margin-bottom: var(--vip-sp-5); }
.bill-exp { margin-left: auto; color: var(--vip-text-muted); font-size: var(--vip-fs-sm); }
</style>
