import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/Button'
import { PageHeader } from '@/components/ui/PageHeader'
import { Pagination } from '@/components/ui/Pagination'
import { Panel } from '@/components/ui/Panel'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { SearchInput } from '@/components/ui/SearchInput'
import { Table } from '@/components/ui/Table'
import type { TableColumn } from '@/components/ui/Table'
import { useToast } from '@/components/ui/ToastProvider'
import { useConfirm } from '@/components/ui/useConfirm'
import { ProductFormModal } from '@/features/products/ProductFormModal'
import { formatMoney } from '@/lib/formatMoney'
import { useClampPage } from '@/lib/useClampPage'
import { toAppError } from '@/services/errors'
import { productService } from '@/services/productService'
import type { Product, ProductCreateInput } from '@/types'

/** Add, edit and delete (archive) the products in Booqable. */
export function ProductsPage() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const rawPage = Number(params.get('page'))
  const page = Number.isInteger(rawPage) && rawPage > 0 ? rawPage : 1
  const [draft, setDraft] = useState(q)
  // `null` = closed, `'new'` = adding, a Product = editing it.
  const [editing, setEditing] = useState<Product | 'new' | null>(null)
  const [formError, setFormError] = useState<string>()

  const toast = useToast()
  const confirm = useConfirm()
  const queryClient = useQueryClient()

  const write = (nextQ: string, nextPage: number) => {
    const search = new URLSearchParams()
    if (nextQ) search.set('q', nextQ)
    if (nextPage > 1) search.set('page', String(nextPage))
    setParams(search, { replace: true })
  }

  const query = useQuery({
    queryKey: ['products', 'list', { q, page }],
    queryFn: () => productService.list({ q, page }),
  })
  useClampPage(query.data, (next) => write(q, next))

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['products'] })

  const save = useMutation({
    mutationFn: (input: ProductCreateInput) =>
      editing && editing !== 'new' ? productService.update(editing.id, input) : productService.create(input),
    onSuccess: async () => {
      const verb = editing === 'new' ? 'added' : 'updated'
      setEditing(null)
      setFormError(undefined)
      await refresh()
      toast.show(`Product ${verb}.`, { tone: 'success' })
    },
    onError: (error) => setFormError(toAppError(error).description),
  })

  const remove = useMutation({
    mutationFn: (id: string) => productService.remove(id),
    onSuccess: async () => {
      await refresh()
      toast.show('Product deleted.', { tone: 'success' })
    },
    onError: (error) => toast.show(toAppError(error).description, { tone: 'danger' }),
  })

  const onDelete = async (product: Product) => {
    const ok = await confirm({
      title: `Delete ${product.name ?? 'this product'}?`,
      description:
        'It will be archived in Booqable and no longer offered to callers. Existing bookings keep their items.',
      confirmLabel: 'Delete',
      tone: 'danger',
    })
    if (ok) remove.mutate(product.id)
  }

  const columns: TableColumn<Product>[] = [
    { id: 'name', header: 'Name', render: (p) => <span className="font-medium text-ink">{p.name ?? 'Unnamed'}</span> },
    { id: 'sku', header: 'SKU', render: (p) => p.sku ?? '—' },
    { id: 'type', header: 'Type', render: (p) => (p.productType ?? '—').replace('_', ' ') },
    {
      id: 'price',
      header: 'Price',
      render: (p) => `${formatMoney(p.price * 100, 'USD')}${p.pricePeriod ? ` / ${p.pricePeriod}` : ''}`,
    },
    { id: 'deposit', header: 'Deposit', render: (p) => formatMoney(p.deposit * 100, 'USD') },
    {
      id: 'actions',
      header: 'Actions',
      visuallyHiddenHeader: true,
      render: (p) => (
        <div className="flex justify-end gap-2">
          <Button
            size="sm"
            variant="ghost"
            aria-label={`Edit ${p.name ?? 'product'}`}
            onClick={() => {
              setFormError(undefined)
              setEditing(p)
            }}
          >
            Edit
          </Button>
          <Button size="sm" variant="danger" aria-label={`Delete ${p.name ?? 'product'}`} onClick={() => void onDelete(p)}>
            Delete
          </Button>
        </div>
      ),
    },
  ]

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader
        title="Products"
        description="The items callers can book. Changes are saved straight to Booqable."
        actions={
          <Button
            onClick={() => {
              setFormError(undefined)
              setEditing('new')
            }}
          >
            Add product
          </Button>
        }
      />
      <div className="space-y-3">
        <SearchInput
          aria-label="Search products"
          placeholder="Search by name or SKU"
          value={draft}
          onChange={setDraft}
          onSearch={(value) => write(value.trim(), 1)}
        />
        <Panel>
          <QueryBoundary
            query={query}
            skeleton="table"
            skeletonRows={6}
            isEmpty={(data) => data.total === 0}
            empty={
              q
                ? { title: 'No matching products', description: 'Try a different name or SKU.' }
                : { title: 'No products yet', description: 'Add your first product to start taking bookings.' }
            }
          >
            {(data) => (
              <>
                <Table columns={columns} rows={data.items} getRowId={(p) => p.id} frame={false} />
                <div className="border-t border-border px-4 py-3">
                  <Pagination page={data.page} pageSize={data.pageSize} total={data.total} onPageChange={(n) => write(q, n)} />
                </div>
              </>
            )}
          </QueryBoundary>
        </Panel>
      </div>
      {editing ? (
        <ProductFormModal
          product={editing === 'new' ? undefined : editing}
          saving={save.isPending}
          error={formError}
          onSave={(input) => save.mutate(input)}
          onClose={() => setEditing(null)}
        />
      ) : null}
    </div>
  )
}
