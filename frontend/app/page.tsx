import Link from "next/link";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ArrowRight, Bot, Target, ShieldCheck } from "lucide-react";

export default function Home() {
  return (
    <main className="flex-1 p-6 md:p-10 max-w-5xl mx-auto space-y-8">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-border pb-6">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Badge variant="outline" className="text-xs">
              Stage 1 Foundation
            </Badge>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            SignalForge AI
          </h1>
          <p className="text-sm text-muted-foreground mt-1 max-w-xl">
            Evidence-driven business intelligence, lead generation, and approved WhatsApp outreach automation.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/login">
            <Button variant="outline">Sign in</Button>
          </Link>
          <Link href="/signup">
            <Button>
              Get started <ArrowRight className="ml-1.5 h-4 w-4" />
            </Button>
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="bg-card border-border">
          <CardHeader>
            <Target className="h-5 w-5 text-primary mb-2" />
            <CardTitle className="text-base font-semibold">Autonomous discovery</CardTitle>
            <CardDescription className="text-sm text-muted-foreground">
              Discovers verified local businesses with Google Places API integration and geo-targeted query generation.
            </CardDescription>
          </CardHeader>
        </Card>

        <Card className="bg-card border-border">
          <CardHeader>
            <Bot className="h-5 w-5 text-primary mb-2" />
            <CardTitle className="text-base font-semibold">Evidence auditing</CardTitle>
            <CardDescription className="text-sm text-muted-foreground">
              Captures real screenshots, runs measured Lighthouse audits, and validates opportunities prior to outreach.
            </CardDescription>
          </CardHeader>
        </Card>

        <Card className="bg-card border-border">
          <CardHeader>
            <ShieldCheck className="h-5 w-5 text-primary mb-2" />
            <CardTitle className="text-base font-semibold">Approved outreach</CardTitle>
            <CardDescription className="text-sm text-muted-foreground">
              Never sends without human approval. Enforces quiet hours, suppression lists, and Twilio delivery rules.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    </main>
  );
}
