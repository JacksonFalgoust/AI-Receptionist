import type { Id, PageRequest, Paginated } from './common'

export type ProductType = 'rental' | 'sales_item' | 'service'
export type TrackingType = 'none' | 'bulk' | 'trackable'
export type PricePeriod = 'minute' | 'hour' | 'day' | 'week' | 'month'

/** A Booqable product group. Prices are in dollars. */
export interface Product {
  id: Id
  name: string | null
  sku: string | null
  description: string | null
  productType: ProductType | null
  trackingType: TrackingType | null
  pricePeriod: PricePeriod | null
  price: number
  deposit: number
  showInStore: boolean
  booqableUrl: string
}

export type ProductsPage = Paginated<Product>

export interface ProductListParams extends PageRequest {
  q?: string
}

/** Fields editable after creation. */
export interface ProductInput {
  name: string
  sku?: string | null
  description?: string | null
  pricePeriod?: PricePeriod
  price?: number
  deposit?: number
  showInStore?: boolean
}

/** Booqable only accepts these when the product is created. */
export interface ProductCreateInput extends ProductInput {
  productType?: ProductType
  trackingType?: TrackingType
}
