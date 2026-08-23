// See https://kit.svelte.dev/docs/types#app
declare global {
  namespace App {
    // interface Error {}
    // interface Locals {}
    // interface PageData {}
    // interface PageState {}
    // interface Platform {}
  }
}

declare module 'jsbarcode' {
  interface JsBarcodeOptions {
    format?: string;
    displayValue?: boolean;
    margin?: number;
    height?: number;
    width?: number;
    lineColor?: string;
    background?: string;
  }

  interface JsBarcode {
    (element: SVGElement, value: string, options?: JsBarcodeOptions): void;
  }

  const JsBarcode: JsBarcode;
  export default JsBarcode;
}

export {};
