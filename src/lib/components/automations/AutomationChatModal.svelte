<script lang="ts">
	import { getContext, tick } from 'svelte';
	import { toast } from 'svelte-sonner';

	const i18n = getContext('i18n');

	import { settings, user as currentUser } from '$lib/stores';
	import { convertMessagesToHistory, createMessagesList } from '$lib/utils';
	import { getUserInfoById } from '$lib/apis/users';
	import { getAutomationChat } from '$lib/apis/automations';

	import Modal from '$lib/components/common/Modal.svelte';
	import Messages from '$lib/components/chat/Messages.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';

	export let show = false;
	export let automationId: string;
	export let chatId: string | null = null;

	let loading = false;
	let loaded = false;

	let chat: any = null;
	let author: any = null;
	let title = '';
	let selectedModels = [''];
	let autoScroll = true;
	let processing = '';

	let messages: any[] = [];
	let history = { messages: {}, currentId: null };

	$: messages = createMessagesList(history, history.currentId);

	const load = async () => {
		loading = true;
		loaded = false;
		try {
			chat = await getAutomationChat(localStorage.token, automationId, chatId);
			if (!chat) {
				toast.error($i18n.t('No chat to show yet.'));
				show = false;
				return;
			}

			// Show the user message author's avatar; fall back to the current user.
			author =
				(await getUserInfoById(localStorage.token, chat.user_id).catch(() => null)) ?? $currentUser;

			const chatContent = chat.chat;
			selectedModels =
				(chatContent?.models ?? undefined) !== undefined
					? chatContent.models
					: [chatContent?.models ?? ''];
			history =
				(chatContent?.history ?? undefined) !== undefined
					? chatContent.history
					: convertMessagesToHistory(chatContent?.messages ?? []);
			title = chatContent?.title ?? '';

			await tick();
			if (messages.length > 0 && messages.at(-1)?.id && messages.at(-1)?.id in history.messages) {
				history.messages[messages.at(-1)?.id].done = true;
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
		load();
	}
</script>

<Modal size="full" bind:show>
	<div class="h-[85vh] flex flex-col text-gray-700 dark:text-gray-100">
		<div class="flex justify-between items-center px-5 pt-4 pb-2 shrink-0">
			<h1 class="text-lg font-medium line-clamp-1 m-0">
				{title || $i18n.t('Automation chat')}
				<span class="text-xs text-gray-400 font-normal ml-2">{$i18n.t('Read-only')}</span>
			</h1>
			<button aria-label={$i18n.t('Close')} on:click={() => (show = false)}>
				<XMark className="size-5" />
			</button>
		</div>

		<div class="flex-1 overflow-auto" id="messages-container">
			{#if loading}
				<div class="flex justify-center items-center h-full"><Spinner /></div>
			{:else if loaded}
				<div class="w-full max-w-5xl mx-auto py-2" role="main">
					<Messages
						className="h-full flex pt-4 pb-8 "
						user={author}
						chatId={chat?.id}
						readOnly={true}
						{selectedModels}
						{processing}
						bind:history
						bind:messages
						bind:autoScroll
						bottomPadding={false}
						sendMessage={() => {}}
						continueResponse={() => {}}
						regenerateResponse={() => {}}
					/>
				</div>
			{/if}
		</div>
	</div>
</Modal>
