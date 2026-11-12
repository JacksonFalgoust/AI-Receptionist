import { matchesSearch, paginate } from '@/mocks/query'
import type {
  Product,
  ProductCreateInput,
  ProductInput,
  ProductListParams,
  ProductsPage,
} from '@/types'

import { delay, isLive } from './config'
import { AppError, isAppError } from './errors'
import { http } from './http'
import { toQueryString } from './queryString'

/** Booqable products (product groups): list, add, edit, delete (archive). */
export interface ProductService {
  list(params?: ProductListParams): Promise<ProductsPage>
  create(input: ProductCreateInput): Promise<Product>
  update(id: string, input: ProductInput): Promise<Product>
  remove(id: string): Promise<void>
}

function fixture(id: string, name: string, sku: string, price: number, deposit: number): Product {
  return {
    id,
    name,
    sku,
    description: null,
    productType: 'rental',
    trackingType: 'bulk',
    pricePeriod: 'day',
    price,
    deposit,
    showInStore: true,
    booqableUrl: `https://example.booqable.com/products/${id}`,
  }
}

let mockProducts: Product[] = []
let mockSeq = 0

export function resetMockProducts(): void {
  mockSeq = 0
  mockProducts = [
    fixture('p1', 'Canoe', 'CAN-1', 45, 100),
    fixture('p2', '6-person Tent', 'TNT-6', 30, 50),
    fixture('p3', 'Paddle', 'PAD-1', 5, 0),
  ]
}
resetMockProducts()

const mockProductService: ProductService = {
  async list(params = {}) {
    await delay()
    const { q, page, pageSize } = params
    const matching = mockProducts
      .filter((p) => matchesSearch([p.name ?? undefined, p.sku ?? undefined], q))
      .sort((a, b) => (a.name ?? '').localeCompare(b.name ?? ''))
    return paginate(matching, { page, pageSize })
  },
  async create(input) {
    await delay()
    const product: Product = {
      ...fixture(`mock-${++mockSeq}`, input.name, input.sku ?? '', input.price ?? 0, input.deposit ?? 0),
      sku: input.sku ?? null,
      description: input.description ?? null,
      productType: input.productType ?? 'rental',
      trackingType: input.trackingType ?? 'bulk',
      pricePeriod: input.pricePeriod ?? 'day',
      showInStore: input.showInStore ?? true,
    }
    mockProducts = [...mockProducts, product]
    return product
  },
  async update(id, input) {
    await delay()
    const existing = mockProducts.find((p) => p.id === id)
    if (!existing) throw notFound()
    const updated = { ...existing, ...input }
    mockProducts = mockProducts.map((p) => (p.id === id ? updated : p))
    return updated
  },
  async remove(id) {
    await delay()
    if (!mockProducts.some((p) => p.id === id)) throw notFound()
    mockProducts = mockProducts.filter((p) => p.id !== id)
  },
}

function notFound(): AppError {
  return new AppError({
    kind: 'not_found',
    title: 'Product not found',
    description: 'This product may already have been removed from Booqable.',
  })
}

/** Keep session expiry and validation errors intact; everything else is Booqable being down. */
function wrap(error: unknown): unknown {
  if (isAppError(error) && ['unauthorized', 'not_found', 'validation'].includes(error.kind)) return error
  return new AppError({
    kind: 'server',
    title: "Couldn't reach Booqable",
    description: 'The change was not saved. Try again in a moment.',
    actions: [{ label: 'Try again', retry: true }],
  })
}

export const httpProductService: ProductService = {
  async list(params = {}) {
    try {
      return await http.get<ProductsPage>(`/products${toQueryString({ ...params })}`)
    } catch (error) {
      throw wrap(error)
    }
  },
  async create(input) {
    try {
      return await http.post<Product>('/products', input)
    } catch (error) {
      throw wrap(error)
    }
  },
  async update(id, input) {
    try {
      return await http.put<Product>(`/products/${encodeURIComponent(id)}`, input)
    } catch (error) {
      throw wrap(error)
    }
  },
  async remove(id) {
    try {
      await http.delete<void>(`/products/${encodeURIComponent(id)}`)
    } catch (error) {
      throw wrap(error)
    }
  },
}

export const productService: ProductService = isLive('products') ? httpProductService : mockProductService
