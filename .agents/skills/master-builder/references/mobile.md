# Mobile app checklist
- Pick one framework (e.g. Flutter or React Native) with pinned versions and confirm it runs on my device or emulator in task 1.
- Handle offline and slow network: caching, retry, clear error states.
- Permissions: ask only when needed, explain why, handle denial.
- Store tokens in secure storage, never plain text. No secrets in the app bundle.
- Responsive for small and large screens, dark mode, safe areas, keyboard not covering inputs.
- Back button and navigation state behave correctly; handle app pause/resume.
- Test on a real device or emulator for every feature. Note platform differences (Android vs iOS).
- Release prep: app icon, name, versioning, signing steps, store requirements.
