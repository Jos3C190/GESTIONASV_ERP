import type {
  Customer,
  CustomerInput,
  CustomerType,
  IdentityDocument
} from '#lib/types/customer.ts';

export const CUSTOMER_TYPE_LABELS: Record<CustomerType, string> = {
  final_consumer: 'Consumidor final',
  taxpayer: 'Contribuyente de IVA',
  foreign: 'Cliente del extranjero'
};

export const IDENTITY_DOCUMENT_LABELS: Record<IdentityDocument, string> = {
  '36': 'NIT',
  '13': 'DUI',
  '02': 'Carné de residente',
  '03': 'Pasaporte',
  '37': 'Otro documento'
};

/** Documentos de identidad que admite cada tipo de cliente. */
export const DOCUMENTS_BY_TYPE: Record<CustomerType, IdentityDocument[]> = {
  final_consumer: ['13', '36', '02', '03', '37'],
  taxpayer: ['36', '13'],
  foreign: ['03', '02', '37']
};

export const RECEIVABLE_DOCUMENT_LABELS: Record<string, string> = {
  '01': 'Factura',
  '03': 'Crédito fiscal',
  '11': 'Factura de exportación'
};

/** Muestra el NIT o DUI con guiones; los demás documentos tal cual. */
export function formatDocument(type: IdentityDocument | null, number: string | null): string {
  if (!type || !number) return '—';
  if (type === '36' && number.length === 14) {
    return `${number.slice(0, 4)}-${number.slice(4, 10)}-${number.slice(10, 13)}-${number.slice(13)}`;
  }
  if ((type === '13' || type === '36') && number.length === 9) {
    return `${number.slice(0, 8)}-${number.slice(8)}`;
  }
  return number;
}

export function formatNrc(nrc: string | null): string {
  if (!nrc) return '—';
  return nrc.length > 1 ? `${nrc.slice(0, -1)}-${nrc.slice(-1)}` : nrc;
}

export function emptyCustomerInput(type: CustomerType = 'final_consumer'): CustomerInput {
  return {
    customer_type: type,
    name: '',
    person_type: type === 'taxpayer' ? '2' : '1',
    taxpayer_category: type === 'taxpayer' ? 'other' : null,
    is_withholding_agent: false,
    commercial_name: null,
    document_type: null,
    document_number: null,
    nrc: null,
    activity_code: null,
    geography: null,
    address_line: null,
    country_code: null,
    phone: null,
    email: null,
    credit_days: 0,
    credit_limit: null,
    seller_employee_id: null,
    price_list_id: null,
    discount_percent: '0'
  };
}

export function customerToInput(customer: Customer): CustomerInput {
  const { address } = customer;
  return {
    customer_type: customer.customer_type,
    name: customer.name,
    person_type: customer.person_type,
    taxpayer_category: customer.taxpayer_category,
    is_withholding_agent: customer.is_withholding_agent,
    commercial_name: customer.commercial_name,
    document_type: customer.document_type,
    document_number: customer.document_number,
    nrc: customer.nrc,
    activity_code: customer.activity_code,
    geography:
      address.department_id && address.municipality_id && address.district_id
        ? {
            department_id: address.department_id,
            municipality_id: address.municipality_id,
            district_id: address.district_id
          }
        : null,
    address_line: customer.address_line,
    country_code: customer.country_code,
    phone: customer.phone,
    email: customer.email,
    credit_days: customer.credit_days,
    credit_limit: customer.credit_limit,
    seller_employee_id: customer.seller_employee_id,
    price_list_id: customer.price_list_id,
    discount_percent: customer.discount_percent
  };
}

/** Ajusta el formulario al cambiar de tipo: quita lo que ese tipo no admite. */
export function switchCustomerType(input: CustomerInput, type: CustomerType): CustomerInput {
  const allowed = DOCUMENTS_BY_TYPE[type];
  const keepDocument = input.document_type !== null && allowed.includes(input.document_type);
  return {
    ...input,
    customer_type: type,
    taxpayer_category: type === 'taxpayer' ? (input.taxpayer_category ?? 'other') : null,
    document_type: keepDocument ? input.document_type : null,
    document_number: keepDocument ? input.document_number : null,
    geography: type === 'foreign' ? null : input.geography,
    country_code: type === 'foreign' ? input.country_code : null
  };
}
