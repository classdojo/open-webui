<script lang="ts">
	import { getContext } from 'svelte';
	const i18n = getContext('i18n');

	import { page } from '$app/stores';
	import { mobile, showSidebar, user } from '$lib/stores';

	import GlobeAlt from '$lib/components/icons/GlobeAlt.svelte';
	import Users from '$lib/components/icons/Users.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';

	export let className = '';
	export let automation: any;

	// classdojo: public = a '*' read grant; shared = any per-user grant.
	$: grants = Array.isArray(automation?.access_grants) ? automation.access_grants : [];
	$: isPublic = grants.some(
		(g) => g?.principal_type === 'user' && g?.principal_id === '*' && g?.permission === 'read'
	);
	$: isShared = grants.some(
		(g) => g?.principal_type === 'user' && g?.principal_id !== '*'
	);
	$: isOwn = automation?.user_id === $user?.id;
</script>

<div
	id="sidebar-automation-item"
	class=" w-full {className} rounded-xl flex relative group hover:bg-gray-100 dark:hover:bg-gray-900 {$page
		.url.pathname === `/automations/${automation.id}`
		? 'bg-gray-100 dark:bg-gray-900 selected'
		: ''} p-1 dark:text-gray-400 text-gray-600 cursor-pointer select-none"
>
	<a
		class=" w-full flex justify-between"
		href="/automations/{automation.id}"
		on:click={() => {
			if ($mobile) {
				showSidebar.set(false);
			}
		}}
		draggable="false"
	>
		<div class="flex items-center gap-1 overflow-hidden">
			<div class=" size-4 justify-center flex items-center ml-1 shrink-0">
				{#if isPublic}
					<Tooltip content={$i18n.t('Public')}>
						<GlobeAlt className="size-3.5" strokeWidth="2" />
					</Tooltip>
				{:else if isShared}
					<Tooltip content={$i18n.t('Shared')}>
						<Users className="size-3.5" strokeWidth="2" />
					</Tooltip>
				{:else}
					<span
						class="inline-block size-1.5 rounded-full {automation?.is_active
							? 'bg-green-500'
							: 'bg-gray-300 dark:bg-gray-700'}"
					></span>
				{/if}
			</div>

			<div class=" text-left self-center overflow-hidden w-full line-clamp-1 flex-1 pr-1">
				<span class="line-clamp-1">{automation?.name}</span>
			</div>
		</div>

		<div class="flex items-center shrink-0">
			{#if !automation?.is_active}
				<span class="text-xs text-gray-400 dark:text-gray-600 pr-1">{$i18n.t('Paused')}</span>
			{:else if !isOwn}
				<span
					class="inline-block size-1.5 rounded-full bg-green-500 self-center mr-1"
					title={$i18n.t('Active')}
				></span>
			{/if}
		</div>
	</a>
</div>
