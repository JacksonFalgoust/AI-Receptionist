import { useState } from 'react'
import type { FormEvent } from 'react'

import { Button } from '@/components/ui/Button'
import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { Modal } from '@/components/ui/Modal'
import { Select } from '@/components/ui/Select'
import { Textarea } from '@/components/ui/Textarea'
import { Toggle } from '@/components/ui/Toggle'
import type {
  PricePeriod,
  Product,
  ProductCreateInput,
  ProductType,
  TrackingType,
} from '@/types'

const PERIODS: PricePeriod[] = ['minute', 'hour', 'day', 'week', 'month']
const TYPES: { value: ProductType; label: string }[] = [
  { value: 'rental', label: 'Rental' },
  { value: 'sales_item', label: 'Sales item' },
  { value: 'service', label: 'Service' },
]
const TRACKING: { value: TrackingType; label: string }[] = [
  { value: 'bulk', label: 'Bulk (count only)' },
  { value: 'trackable', label: 'Trackable (each item identified)' },
  { value: 'none', label: 'None (services)' },
]

export interface ProductFormModalProps {
  /** The product being edited; omit to add a new one. */
  product?: Product
  saving: boolean
  error?: string
  onSave: (input: ProductCreateInput) => void
  onClose: () => void
}

export function ProductFormModal({ product, saving, error, onSave, onClose }: ProductFormModalProps) {
  const editing = Boolean(product)
  const [name, setName] = useState(product?.name ?? '')
  const [sku, setSku] = useState(product?.sku ?? '')
  const [description, setDescription] = useState(product?.description ?? '')
  const [price, setPrice] = useState(String(product?.price ?? 0))
  const [deposit, setDeposit] = useState(String(product?.deposit ?? 0))
  const [period, setPeriod] = useState<PricePeriod>(product?.pricePeriod ?? 'day')
  const [showInStore, setShowInStore] = useState(product?.showInStore ?? true)
  const [productType, setProductType] = useState<ProductType>(product?.productType ?? 'rental')
  const [trackingType, setTrackingType] = useState<TrackingType>(product?.trackingType ?? 'bulk')
  const [touched, setTouched] = useState(false)

  const priceNum = Number(price)
  const depositNum = Number(deposit)
  const nameError = !name.trim() ? 'Name is required.' : undefined
  const priceError = !Number.isFinite(priceNum) || priceNum < 0 ? 'Enter a price of 0 or more.' : undefined
  const depositError =
    !Number.isFinite(depositNum) || depositNum < 0 ? 'Enter a deposit of 0 or more.' : undefined

  const submit = (event: FormEvent) => {
    event.preventDefault()
    setTouched(true)
    if (nameError || priceError || depositError) return
    onSave({
      name: name.trim(),
      sku: sku.trim() || null,
      description: description.trim() || null,
      price: priceNum,
      deposit: depositNum,
      pricePeriod: period,
      showInStore,
      ...(editing ? {} : { productType, trackingType }),
    })
  }

  return (
    <Modal
      isOpen
      onClose={onClose}
      title={editing ? 'Edit product' : 'Add product'}
      actions={
        <>
          <Button variant="ghost" type="button" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" form="product-form" disabled={saving}>
            {saving ? 'Saving…' : editing ? 'Save changes' : 'Add product'}
          </Button>
        </>
      }
    >
      <form id="product-form" onSubmit={submit} noValidate className="mt-3">
        {error ? (
          <p role="alert" className="mb-3 text-sm text-danger">
            {error}
          </p>
        ) : null}
        <Field label="Name" htmlFor="product-name" error={touched ? nameError : undefined}>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="SKU" htmlFor="product-sku">
          <Input value={sku} onChange={(e) => setSku(e.target.value)} />
        </Field>
        <Field label="Description" htmlFor="product-description">
          <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Price (USD)" htmlFor="product-price" error={touched ? priceError : undefined}>
            <Input type="number" min="0" step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} />
          </Field>
          <Field label="Per" htmlFor="product-period">
            <Select
              value={period}
              onChange={(e) => setPeriod(e.target.value as PricePeriod)}
              options={PERIODS.map((p) => ({ value: p, label: p }))}
            />
          </Field>
        </div>
        <Field label="Deposit (USD)" htmlFor="product-deposit" error={touched ? depositError : undefined}>
          <Input type="number" min="0" step="0.01" value={deposit} onChange={(e) => setDeposit(e.target.value)} />
        </Field>
        {editing ? null : (
          <div className="grid grid-cols-2 gap-3">
            <Field label="Type" htmlFor="product-type" description="Can't be changed later.">
              <Select
                value={productType}
                onChange={(e) => setProductType(e.target.value as ProductType)}
                options={TYPES}
              />
            </Field>
            <Field label="Tracking" htmlFor="product-tracking" description="Can't be changed later.">
              <Select
                value={trackingType}
                onChange={(e) => setTrackingType(e.target.value as TrackingType)}
                options={TRACKING}
              />
            </Field>
          </div>
        )}
        <Toggle label="Show in online store" checked={showInStore} onChange={(e) => setShowInStore(e.target.checked)} />
      </form>
    </Modal>
  )
}
