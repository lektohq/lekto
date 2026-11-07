/**
 * Installing the app from within it (web/DESIGN.md, "App"). Chrome and Edge offer it through
 * `beforeinstallprompt`, which this keeps for a button of Lekto's own; Safari has no such event
 * (there it is the share menu's "Zum Home-Bildschirm").
 */

interface InstallPromptEvent extends Event {
	prompt(): Promise<void>;
	userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

class Install {
	#prompt = $state<InstallPromptEvent | null>(null);

	/** Whether the browser would install the app now. */
	get available(): boolean {
		return this.#prompt !== null;
	}

	/** Ask the browser to install the app; its own dialog asks the person. */
	async ask(): Promise<void> {
		const prompt = this.#prompt;
		if (!prompt) return;
		this.#prompt = null;
		await prompt.prompt();
	}

	/** Listen for the browser's offer; once, when the app starts. */
	watch(): void {
		window.addEventListener('beforeinstallprompt', (event) => {
			event.preventDefault();
			this.#prompt = event as InstallPromptEvent;
		});
		window.addEventListener('appinstalled', () => (this.#prompt = null));
	}
}

export const install = new Install();

/** Android: the share sheet takes an installed app (the manifest's `share_target`). */
export function isAndroid(): boolean {
	return /Android/i.test(navigator.userAgent);
}
