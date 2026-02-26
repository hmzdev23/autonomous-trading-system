import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
    title: 'HR Capital — Dashboard',
    description: 'Autonomous hedge fund trading dashboard',
};

export default function RootLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <html lang="en">
            <body>{children}</body>
        </html>
    );
}
