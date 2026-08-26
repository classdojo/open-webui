<script lang="ts">
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import type i18nType from '$lib/i18n';

	import { getAutomationChat, type AutomationChatMessage } from '$lib/apis/automations';
	import { createMessagesList } from '$lib/utils';
	import Markdown from '$lib/components/chat/Messages/Markdown.svelte';
	import Modal from '$lib/components/common/Modal.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';

	const i18n: typeof i18nType = getContext('i18n');

	export let show = false;
	export let automationId: string;
	export let chatId: string | null = null;

	let loading = false;
	let loaded = false;
	let loadedKey = '';
	let title = '';
	let messages: AutomationChatMessage[] = [];

	const load = async () => {
		loading = true;
		loaded = false;
		messages = [];
		title = '';
		try {
			const chat = await getAutomationChat(localStorage.token, automationId, chatId);
			const content = chat?.chat ?? {};
			title = content.title ?? '';
			if (content.history?.messages && content.history?.currentId) {
				messages = createMessagesList(content.history, content.history.currentId);
			} else if (Array.isArray(content.messages)) {
				messages = content.messages.map((message, index) => ({
					id: `m${index}`,
					...message
				}));
			}
			loaded = true;
		} catch (error: unknown) {
			const detail =
				typeof error === 'object' && error && 'detail' in error
					? String(error.detail)
					: String(error);
			toast.error(detail);
			show = false;
		} finally {
			loading = false;
		}
	};

	$: if (show && automationId) {
		const key = `${automationId}:${chatId ?? 'latest'}`;
		if (key !== loadedKey) {
			loadedKey = key;
			load();
		}
	}
	$: if (!show) loadedKey = '';
</script>

<Modal size="lg" bind:show>
	<div class="flex max-h-[85vh] flex-col text-gray-700 dark:text-gray-100">
		<div class="flex shrink-0 items-center justify-between px-5 pb-2 pt-4">
			<h1 class="m-0 line-clamp-1 text-lg font-medium">
				{title || $i18n.t('Automation chat')}
				<span class="ml-2 text-xs font-normal text-gray-400">{$i18n.t('Read-only')}</span>
			</h1>
			<button aria-label={$i18n.t('Close')} on:click={() => (show = false)}>
				<XMark className="size-5" />
			</button>
		</div>

		<div class="flex-1 space-y-5 overflow-auto px-5 pb-5">
			{#if loading}
				<div class="flex justify-center py-10"><Spinner /></div>
			{:else if loaded}
				{#if messages.length === 0}
					<div class="py-6 text-center text-sm text-gray-500">
						{$i18n.t('This chat has no messages.')}
					</div>
				{/if}
				{#each messages as message (message.id)}
					<div class="flex flex-col gap-1">
						<div class="text-xs font-medium uppercase text-gray-400">
							{message.role === 'user' ? $i18n.t('User') : message.model || $i18n.t('Assistant')}
						</div>
						<div class="text-sm">
							<Markdown id={message.id} content={message.content ?? ''} />
						</div>
					</div>
				{/each}
			{/if}
		</div>
	</div>
</Modal>
