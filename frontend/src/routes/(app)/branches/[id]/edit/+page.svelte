<script lang="ts">
  import { page } from '$app/state';
  import BranchEditor from '$lib/features/branches/components/BranchEditor.svelte';
</script>

<BranchEditor mode="edit" branchId={page.params.id} />
