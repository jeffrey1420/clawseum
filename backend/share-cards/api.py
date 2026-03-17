"""
CLAWSEUM Share Card API
FastAPI endpoints for generating social media share cards
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import asyncio
from pathlib import Path

from .generator import CardGenerator
from .renderer import CardRenderer


# Request models
class BetrayalRequest(BaseModel):
    betrayer: str = Field(..., description="Name of the agent who betrayed")
    victim: str = Field(..., description="Name of the agent who was betrayed")
    mission: str = Field(..., description="Mission name or description")
    timestamp: str = Field(..., description="ISO timestamp of the betrayal")


class VictoryRequest(BaseModel):
    winner: str = Field(..., description="Name of the winning agent")
    losers: List[str] = Field(..., description="List of losing agent names")
    mission: str = Field(..., description="Mission name or description")
    stats: Dict[str, Any] = Field(..., description="Game statistics (e.g., duration, score)")


class AllianceRequest(BaseModel):
    agent1: str = Field(..., description="Name of first agent")
    agent2: str = Field(..., description="Name of second agent")
    duration: str = Field(..., description="How long the alliance lasted")


class UpsetRequest(BaseModel):
    underdog: str = Field(..., description="Name of the underdog who won")
    favorite: str = Field(..., description="Name of the favorite who lost")
    margin: str = Field(..., description="Victory margin description")


# Initialize FastAPI app
app = FastAPI(
    title="CLAWSEUM Share Cards API",
    description="Generate shareable social media cards for CLAWSEUM game events",
    version="1.0.0"
)

# Initialize generator and renderer
generator = CardGenerator()
renderer = CardRenderer()


@app.on_event("startup")
async def startup_event():
    """Start the renderer on app startup"""
    await renderer.start()


@app.on_event("shutdown")
async def shutdown_event():
    """Close the renderer on app shutdown"""
    await renderer.close()


@app.post("/share/betrayal", response_class=Response)
async def create_betrayal_card(request: BetrayalRequest):
    """
    Generate a betrayal announcement card
    
    Returns PNG image (1200x675)
    """
    try:
        # Generate HTML
        html = generator.generate_betrayal_card(
            betrayer=request.betrayer,
            victim=request.victim,
            mission=request.mission,
            timestamp=request.timestamp
        )
        
        # Render to PNG
        image_bytes = await renderer.render(html, return_base64=False, use_cache=True)
        
        # Read the file and return as response
        with open(image_bytes, 'rb') as f:
            image_data = f.read()
        
        return Response(
            content=image_data,
            media_type="image/png",
            headers={
                "Content-Disposition": "inline; filename=betrayal.png"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/share/victory", response_class=Response)
async def create_victory_card(request: VictoryRequest):
    """
    Generate a victory celebration card
    
    Returns PNG image (1200x675)
    """
    try:
        # Generate HTML
        html = generator.generate_victory_card(
            winner=request.winner,
            losers=request.losers,
            mission=request.mission,
            stats=request.stats
        )
        
        # Render to PNG
        image_bytes = await renderer.render(html, return_base64=False, use_cache=True)
        
        # Read the file and return as response
        with open(image_bytes, 'rb') as f:
            image_data = f.read()
        
        return Response(
            content=image_data,
            media_type="image/png",
            headers={
                "Content-Disposition": "inline; filename=victory.png"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/share/leaderboard/{axis}", response_class=Response)
async def create_leaderboard_card(
    axis: str,
    agents: str,
    scores: str
):
    """
    Generate a leaderboard ranking card
    
    Query parameters:
    - axis: Ranking category (e.g., "Wins", "Betrayals", "Trust Score")
    - agents: Comma-separated list of agent names
    - scores: Comma-separated list of scores (must match agent count)
    
    Returns PNG image (1200x675)
    """
    try:
        # Parse agents and scores
        agent_names = [name.strip() for name in agents.split(',')]
        score_values = [score.strip() for score in scores.split(',')]
        
        if len(agent_names) != len(score_values):
            raise HTTPException(
                status_code=400,
                detail="Number of agents must match number of scores"
            )
        
        # Build agent list
        top_agents = [
            {"name": name, "score": score}
            for name, score in zip(agent_names, score_values)
        ]
        
        # Generate HTML
        html = generator.generate_leaderboard_card(
            top_agents=top_agents,
            axis=axis
        )
        
        # Render to PNG
        image_bytes = await renderer.render(html, return_base64=False, use_cache=True)
        
        # Read the file and return as response
        with open(image_bytes, 'rb') as f:
            image_data = f.read()
        
        return Response(
            content=image_data,
            media_type="image/png",
            headers={
                "Content-Disposition": "inline; filename=leaderboard.png"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/share/alliance", response_class=Response)
async def create_alliance_card(request: AllianceRequest):
    """
    Generate an alliance formation card
    
    Returns PNG image (1200x675)
    """
    try:
        # Generate HTML
        html = generator.generate_alliance_card(
            agent1=request.agent1,
            agent2=request.agent2,
            duration=request.duration
        )
        
        # Render to PNG
        image_bytes = await renderer.render(html, return_base64=False, use_cache=True)
        
        # Read the file and return as response
        with open(image_bytes, 'rb') as f:
            image_data = f.read()
        
        return Response(
            content=image_data,
            media_type="image/png",
            headers={
                "Content-Disposition": "inline; filename=alliance.png"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/share/upset", response_class=Response)
async def create_upset_card(request: UpsetRequest):
    """
    Generate an upset victory card
    
    Returns PNG image (1200x675)
    """
    try:
        # Generate HTML
        html = generator.generate_upset_card(
            underdog=request.underdog,
            favorite=request.favorite,
            margin=request.margin
        )
        
        # Render to PNG
        image_bytes = await renderer.render(html, return_base64=False, use_cache=True)
        
        # Read the file and return as response
        with open(image_bytes, 'rb') as f:
            image_data = f.read()
        
        return Response(
            content=image_data,
            media_type="image/png",
            headers={
                "Content-Disposition": "inline; filename=upset.png"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "share-cards"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
