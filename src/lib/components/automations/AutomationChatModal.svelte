<script lang="ts">
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';

	const i18n = getContext('i18n');

	import { createMessagesList } from '$lib/utils';
	import { getAutomationChat } from '$lib/apis/automations';

	import Modal from '$lib/components/common/Modal.svelte';
	import Markdown from '$lib/components/chat/Messages/Markdown.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';

	export let show = false;
	export let automationId: string;
	export let chatId: string | null = null;

	let loading = false;
	let loaded = false;
	let title = '';
	let messages: any[] = [];
	// classdojo: guards the load reactive so it runs once per open and never
	// re-enters (a heavy re-render must not re-trigger the fetch in a loop).
	let loadedKey = '';

	const load = async () => {
		loading = true;
		loaded = false;
		messages = [];
		title = '';
		try {
			const chat = await getAutomationChat(localStorage.token, automationId, chatId);
			if (!chat) {
				toast.error($i18n.t('No chat to show yet.'));
				show = false;
				return;
			}
			const content = chat.chat ?? {};
			title = content?.title ?? '';

			if (content?.history?.messages && content?.history?.currentId) {
				messages = createMessagesList(content.history, content.history.currentId);
			} else if (Array.isArray(content?.messages)) {
				messages = content.messages.map((m: any, i: number) => ({ id: `m${i}`, ...m }));
			} else {
				messages = [];
			}
			loaded = true;
		} catch (e: any) {
			toast.error(e?.detail ?? `${e}` ?? 'Failed to load chat');
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
	$: if (!show) {
		loadedKey = '';
	}
</script>

<Modal size="lg" bind:show>
	<div class="flex flex-col max-h-[85vh] text-gray-700 dark:text-gray-100">
		<div class="flex justify-between items-center px-5 pt-4 pb-2 shrink-0">
			<h1 class="text-lg font-medium line-clamp-1 m-0">
				{title || $i18n.t('Automation chat')}
				<span class="text-xs text-gray-400 font-normal ml-2">{$i18n.t('Read-only')}</span>
			</h1>
			<button aria-label={$i18n.t('Close')} on:click={() => (show = false)}>
				<XMark className="size-5" />
			</button>
		</div>

		<div class="flex-1 overflow-auto px-5 pb-5 space-y-5">
			{#if loading}
				<div class="flex justify-center py-10"><Spinner /></div>
			{:else if loaded}
				{#if messages.length === 0}
					<div class="text-sm text-gray-500 py-6 text-center">
						{$i18n.t('This chat has no messages.')}
					</div>
				{/if}
				{#each messages as message (message.id)}
					<div class="flex flex-col gap-1">
						<div class="text-xs font-medium text-gray-400 uppercase">
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
