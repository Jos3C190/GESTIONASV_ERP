<script lang="ts">
  import { page } from '$app/state';
  import CustomerForm from '$lib/features/customers/components/CustomerForm.svelte';
</script>

{#key page.params.id}
  <CustomerForm customerId={page.params.id} />
{/key}
